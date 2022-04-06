"""ACA-Py Event to Redis."""

import json
import logging
import re
from string import Template
from typing import Optional, cast

from aries_cloudagent.core.event_bus import Event, EventBus, EventWithMetadata
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.core.util import SHUTDOWN_EVENT_PATTERN, STARTUP_EVENT_PATTERN
from aries_cloudagent.config.injection_context import InjectionContext
from redis.cluster import RedisCluster as Redis
from redis.exceptions import RedisError

from ..config import get_config, EventsConfig


LOGGER = logging.getLogger(__name__)


async def setup(context: InjectionContext):
    """Setup the plugin."""
    config = get_config(context.settings).events
    if not config:
        config = EventsConfig.default()

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
    config = get_config(profile.settings).events or EventsConfig.default()
    redis = Redis.from_url(**config.producer.dict())
    profile.context.injector.bind_instance(Redis, redis)


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
    redis = profile.inject(Redis)

    LOGGER.info("Handling event: %s", event)
    wallet_id = cast(Optional[str], profile.settings.get("wallet.id"))
    payload = {
        "wallet_id": wallet_id or "base",
        "state": event.payload.get("state"),
        "topic": event.topic,
        "category": _derive_category(event.topic),
        "payload": event.payload,
    }
    config = get_config(profile.settings).events or EventsConfig.default()
    try:
        template = config.topic_maps[event.metadata.pattern.pattern]
        topic = Template(template).substitute(**payload)
        LOGGER.info(f"Sending message {payload} with topic {topic}")        
        redis.rpush(
            topic, str.encode(json.dumps(payload)),
        )
    except Exception:
        LOGGER.exception("Redis failed to send message")
