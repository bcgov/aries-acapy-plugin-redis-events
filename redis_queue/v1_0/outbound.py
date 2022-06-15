"""Basic in memory queue."""
import base64
import json

from aries_cloudagent.core.profile import Profile
from .config import OutboundConfig
import logging
from typing import List, Optional, Union

from aries_cloudagent.transport.outbound.base import (
    BaseOutboundTransport,
    OutboundTransportError,
)
from aries_cloudagent.transport.wire_format import (
    DIDCOMM_V0_MIME_TYPE,
    DIDCOMM_V1_MIME_TYPE,
)

from redis.cluster import RedisCluster as Redis
from redis.exceptions import RedisError

from . import get_config


LOGGER = logging.getLogger(__name__)


def b64_to_bytes(val: Union[str, bytes], urlsafe=False) -> bytes:
    """Convert a base 64 string to bytes."""
    if isinstance(val, str):
        val = val.encode("ascii")
    if urlsafe:
        missing_padding = len(val) % 4
        if missing_padding:
            val += b"=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(val)
    return base64.b64decode(val)


class RedisOutboundQueue(BaseOutboundTransport):
    """Redis queue implementation class."""

    DEFAULT_OUTBOUND_TOPIC = "acapy-outbound-message"
    schemes = ("redis", "rediss")

    def __init__(self, profile: Profile):
        """Initialize base queue type."""
        super().__init__(profile)
        self.config = get_config(profile.settings).outbound or OutboundConfig.default()
        LOGGER.info(
            f"Setting up redis outbound queue with configuration: {self.config}"
        )
        self.redis = None

    async def start(self):
        """Start the queue."""
        LOGGER.info("Starting redis outbound queue producer")
        self.redis = Redis.from_url(**self.config.producer.dict())

    async def stop(self):
        """Stop the queue."""
        pass

    async def handle_message(
        self,
        profile: Profile,
        payload: Union[str, bytes],
        endpoint: str,
        metadata: dict = None,
        api_key: str = None,
    ):
        """Prepare and send message to external queue."""
        if not self.redis:
            raise OutboundTransportError("No Redis instance setup")
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
        topic = self.config.topic
        message = str.encode(
            json.dumps(
                {
                    "service": {"url": endpoint},
                    "payload": base64.urlsafe_b64encode(payload).decode(),
                    "headers": headers,
                }
            ),
        )
        try:
            LOGGER.info(
                "  - Adding outbound message to Redis: (%s): %s",
                topic,
                message,
            )
            return self.redis.send_and_wait(topic, message)
        except Exception:
            LOGGER.exception("Error while pushing to Redis")
