import asyncio
import base64
import json
from json import JSONDecodeError
import logging
from typing import cast

from aries_cloudagent.messaging.error import MessageParseError
from aries_cloudagent.transport.error import WireFormatParseError
from aries_cloudagent.transport.inbound.base import BaseInboundTransport
from aries_cloudagent.transport.wire_format import (
    DIDCOMM_V0_MIME_TYPE,
    DIDCOMM_V1_MIME_TYPE,
)
from redis.cluster import RedisCluster as Redis
from redis.exceptions import RedisError

from .config import get_config, InboundConfig

LOGGER = logging.getLogger(__name__)


class RedisInboundTransport(BaseInboundTransport):
    """Inbound Transport using Redis."""

    def __init__(self, host: str, port: int, create_session, **kwargs) -> None:
        """
        Initialize an inbound HTTP transport instance.

        Args:
            host: Host to listen on
            port: Port to listen on
            create_session: Method to create a new inbound session

        """
        super().__init__("redis", create_session, **kwargs)
        self.host = host
        self.port = port
        self.running = True
        config = (
            get_config(self.root_profile.context.settings).inbound
            or InboundConfig.default()
        )
        self.redis = Redis.from_url(self.host)
        self.inbound_topic = config.topics[0]
        self.direct_response_topic = config.topics[1]

    async def start(self):
        while self.running:
            msg_received = False
            retry_pop_count = 0
            while not msg_received:
                try:
                    msg = self.redis.blpop(self.inbound_topic, 0.2)
                    msg_received = True
                    retry_pop_count = 0
                except RedisError as err:
                    await asyncio.sleep(1)
                    LOGGER.warning(err)
                    retry_pop_count = retry_pop_count + 1
                    if retry_pop_count > 5:
                        LOGGER.exception(f"Unexpected exception {str(err)}")
            if not msg:
                await asyncio.sleep(1)
                continue
            msg = msg[1]
            if not isinstance(msg, dict):
                LOGGER.error("Received non-dict message")
                continue
            try:
                direct_reponse_requested = True if "txn_id" in msg else False
                inbound = json.loads(msg)
                transport_type = inbound.get("transport_type")
                payload = base64.urlsafe_b64decode(inbound["payload"])

                session = await self.create_session(
                    accept_undelivered=False, can_respond=False
                )

                async with session:
                    await session.receive(cast(bytes, payload))
                    if direct_reponse_requested:
                        txn_id = msg["txn_id"]
                        response = await session.wait_response()
                        response_data = {}
                        if transport_type == "http" and response:
                            if isinstance(response, bytes):
                                if session.profile.settings.get(
                                    "emit_new_didcomm_mime_type"
                                ):
                                    response_data["content-type"] = DIDCOMM_V1_MIME_TYPE
                                else:
                                    response_data["content-type"] = DIDCOMM_V0_MIME_TYPE
                            else:
                                response_data["content-type"] = "application/json"
                        response_data["response"] = response
                        message = {}
                        message["txn_id"] = txn_id
                        message["response_data"] = response_data
                        try:
                            self.redis.rpush(
                                self.direct_response_topic,
                                str.encode(json.dumps(message)),
                            )
                        except RedisError as err:
                            LOGGER.exception(f"Unexpected exception {str(err)}")

            except (JSONDecodeError, KeyError):
                LOGGER.exception("Received invalid inbound message record")
            except (MessageParseError, WireFormatParseError):
                LOGGER.exception("Failed to process message")

    async def stop(self):
        pass
