"""Basic in memory queue."""
import asyncio
import base64
import json

from aries_cloudagent.core.profile import Profile
from .config import OutboundConfig
import logging
from typing import List, Optional, Union
from .utils import (
    process_payload_recip_key,
)

from aries_cloudagent.transport.outbound.base import (
    BaseOutboundTransport,
    OutboundTransportError,
)
from aries_cloudagent.transport.wire_format import (
    DIDCOMM_V0_MIME_TYPE,
    DIDCOMM_V1_MIME_TYPE,
)

from redis.asyncio import RedisCluster
from redis.exceptions import RedisError
from uuid import uuid4

from . import get_config


LOGGER = logging.getLogger(__name__)


class RedisOutboundQueue(BaseOutboundTransport):
    """Redis queue implementation class."""

    DEFAULT_OUTBOUND_TOPIC = "acapy_outbound"
    schemes = "redis"
    is_external = False

    def __init__(self, root_profile: Profile):
        """Initialize base queue type."""
        super().__init__(root_profile)
        self.outbound_config = (
            get_config(root_profile.context.settings).outbound
            or OutboundConfig.default()
        )
        LOGGER.info(
            f"Setting up redis outbound queue with configuration: {self.outbound_config}"
        )
        self.redis = root_profile.inject(RedisCluster)
        self.is_mediator = self.outbound_config.mediator_mode
        self.outbound_topic = self.outbound_config.acapy_outbound_topic

    async def start(self):
        """Start the queue."""

    async def stop(self):
        """Stop the queue."""

    async def handle_message(
        self,
        profile: Profile,
        payload: Union[str, bytes],
        endpoint: str,
        metadata: dict = None,
        api_key: str = None,
    ):
        """Prepare and send message to external queue."""
        if not endpoint:
            raise OutboundTransportError("No endpoint provided")
        headers = metadata or {}
        if api_key is not None:
            headers["x-api-key"] = api_key
        if isinstance(payload, bytes):
            if profile.settings.get("emit_new_didcomm_mime_type"):
                headers["Content-Type"] = DIDCOMM_V1_MIME_TYPE
            else:
                headers["Content-Type"] = DIDCOMM_V0_MIME_TYPE
        else:
            headers["Content-Type"] = "application/json"
            payload = payload.encode("utf-8")
        topic = self.outbound_topic
        message = str.encode(
            json.dumps(
                {
                    "service": {"url": endpoint},
                    "payload": base64.urlsafe_b64encode(payload).decode(),
                    "headers": headers,
                }
            ),
        )
        if self.is_mediator:
            topic, message = await process_payload_recip_key(self.redis, payload, topic)
        try:
            LOGGER.info(
                "  - Adding outbound message to Redis: (%s): %s",
                topic,
                message,
            )
            await self.redis.rpush(
                topic,
                message,
            )
        except RedisError:
            LOGGER.exception("Error while pushing to Redis")
