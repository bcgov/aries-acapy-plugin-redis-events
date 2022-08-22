"""ACA-Py Event to Redis."""

import json
import logging
import base64
import re
from string import Template
from typing import Optional, cast

from aries_cloudagent.core.event_bus import Event, EventBus, EventWithMetadata
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.core.util import SHUTDOWN_EVENT_PATTERN, STARTUP_EVENT_PATTERN
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.transport.error import TransportError
from redis.asyncio import RedisCluster
from redis.exceptions import RedisError

from ..config import OutboundConfig, get_config, EventConfig

LOGGER = logging.getLogger(__name__)


async def setup(context: InjectionContext):
    """Setup the plugin."""
    config = get_config(context.settings).event or EventConfig.default()

    bus = context.inject(EventBus)
    if not bus:
        raise ValueError("EventBus missing in context")

    for event in config.topic_maps.keys():
        LOGGER.info(f"subscribing to event: {event}")
        bus.subscribe(re.compile(event), handle_event)

    bus.subscribe(STARTUP_EVENT_PATTERN, on_startup)
    bus.subscribe(SHUTDOWN_EVENT_PATTERN, on_shutdown)


RECORD_RE = re.compile(r"acapy::record::([^:]*)(?:::(.*))?")
WEBHOOK_RE = re.compile(r"acapy::webhook::{.*}")


async def on_startup(profile: Profile, event: Event):
    connection_url = (get_config(profile.settings).connection).connection_url
    try:
        redis = RedisCluster.from_url(url=connection_url)
    except RedisError as err:
        raise TransportError(f"No Redis instance setup, {err}")
    profile.context.injector.bind_instance(RedisCluster, redis)


async def on_shutdown(profile: Profile, event: Event):
    pass


def _derive_category(topic: str):
    match = RECORD_RE.match(topic)
    if match:
        return match.group(1)
    if WEBHOOK_RE.match(topic):
        return "webhook"


async def handle_event(profile: Profile, event: EventWithMetadata):
    """Push events from aca-py events."""
    redis = profile.inject(RedisCluster)

    LOGGER.info("Handling event: %s", event)
    wallet_id = cast(Optional[str], profile.settings.get("wallet.id"))
    payload = {
        "wallet_id": wallet_id or "base",
        "state": event.payload.get("state"),
        "topic": event.topic,
        "category": _derive_category(event.topic),
        "payload": event.payload,
    }
    try:
        config = get_config(profile.settings).event or EventConfig.default()
        template = config.topic_maps[event.metadata.pattern.pattern]
        kafka_topic = Template(template).substitute(**payload)
        LOGGER.info(f"Sending message {payload} with Kafka topic {kafka_topic}")
        outbound = str.encode(
            json.dumps(
                {
                    "payload": payload,
                    "metadata": {"x-wallet-id": wallet_id} if wallet_id else {},
                }
            ),
        )
        await redis.rpush(
            kafka_topic,
            outbound,
        )
    except (RedisError, ValueError) as err:
        LOGGER.exception(f"Failed to process and send webhook, {err}")
