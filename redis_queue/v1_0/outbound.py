"""Basic in memory queue."""
import asyncio
import base64
import json

from aries_cloudagent.core.profile import Profile
from .config import OutboundConfig
import logging
from typing import List, Optional, Union
from utils import (
    b64_to_bytes,
    _recipients_from_packed_message,
    get_timedelta_seconds,
    str_to_datetime,
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

    DEFAULT_OUTBOUND_TOPIC = "acapy-outbound"
    schemes = ("redis", "rediss")
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
        self.redis = self.root_profile.inject(RedisCluster)
        self.is_mediator = self.outbound_config.mediator_mode
        self.outbound_topic = self.outbound_config.acapy_outbound_topic

    async def start(self):
        """Start the queue."""

    async def stop(self):
        """Stop the queue."""

    async def get_recip_keys_list_for_uid(self, plugin_uid: bytes):
        """Get recip_keys list associated with plugin UID."""
        recip_keys_encoded = await self.redis.hget("uid_recip_keys_map", plugin_uid)
        if not recip_keys_encoded:
            return []
        inbound_msg_keys = json.loads(b64_to_bytes(recip_keys_encoded).decode())
        return inbound_msg_keys

    async def get_new_valid_uid(self, to_ignore_uid: bytes = None):
        """Get a new plugin UID for recip_key assignment/reassignment."""
        new_uid = None
        uid_not_selected = False
        while not uid_not_selected:
            if not await self.redis.get("round_robin_iterator"):
                await self.redis.set("round_robin_iterator", 0)
            next_iter = int((await self.redis.get("round_robin_iterator")).decode())
            uid_list = await self.redis.hkeys("uid_recip_keys_map")
            if to_ignore_uid:
                try:
                    uid_list.remove(to_ignore_uid)
                except KeyError:
                    pass
            if len(uid_list) == 0:
                print("Raise Error, no plugin instance available")
                await asyncio.sleep(15)
                continue
            try:
                new_uid = uid_list[next_iter]
            except IndexError:
                new_uid = uid_list[0]
            next_iter = next_iter + 1
            if next_iter < len(uid_list):
                await self.redis.set("round_robin_iterator", next_iter)
            else:
                await self.redis.set("round_robin_iterator", 0)
            uid_not_selected = True
        return new_uid

    async def assign_recip_key_to_new_uid(self, recip_key: bytes):
        """Assign recip_key to a new plugin UID."""
        new_uid = await self.get_new_valid_uid()
        await self.redis.hset("recip_key_uid_map", recip_key, new_uid)
        recip_keys_list = await self.get_recip_keys_list(new_uid)
        recip_keys_set = set(recip_keys_list)
        if recip_key not in recip_keys_set:
            recip_keys_set.add(recip_key)
            new_recip_keys_set = base64.urlsafe_b64encode(
                json.dumps(list(recip_keys_set)).encode("utf-8")
            ).decode()
            await self.redis.hset("uid_recip_keys_map", new_uid, new_recip_keys_set)
        await self.redis.hset("recip_key_uid_map", recip_key.encode("utf-8"), new_uid)
        uid_recip_key = f"{new_uid.decode()}_{recip_key}".encode("utf-8")
        await self.redis.hset("uid_recip_key_pending_msg_count", uid_recip_key, 0)
        return new_uid.decode()

    async def reassign_recip_key_to_uid(self, old_uid: bytes, recip_key: bytes):
        """Reassign recip_key from old_uid to a new plugin UID."""
        new_uid = await self.get_new_valid_uid(old_uid)
        old_recip_keys_list = await self.get_recip_keys_list(old_uid)
        new_recip_keys_list = await self.get_recip_keys_list(new_uid)
        old_recip_keys_set = set(old_recip_keys_list)
        try:
            old_recip_keys_set.remove(recip_key)
            await self.redis.hset(
                "uid_recip_keys_map",
                old_uid,
                base64.urlsafe_b64encode(
                    json.dumps(list(old_recip_keys_set)).encode("utf-8")
                ).decode(),
            )
        except KeyError:
            pass
        old_uid_recip_key = f"{old_uid.decode()}_{recip_key}".encode("utf-8")
        old_pending_msg_count = await self.redis.hget(
            "uid_recip_key_pending_msg_count", old_uid_recip_key
        )
        await self.redis.hdel("uid_recip_key_pending_msg_count", old_uid_recip_key)
        await self.redis.hset("recip_key_uid_map", recip_key, new_uid)
        new_recip_keys_set = set(new_recip_keys_list)
        new_recip_keys_set.add(recip_key)
        new_recip_keys_set = base64.urlsafe_b64encode(
            json.dumps(list(new_recip_keys_set)).encode("utf-8")
        ).decode()
        await self.redis.hset("uid_recip_keys_map", new_uid, new_recip_keys_set)
        new_uid_recip_key = f"{new_uid.decode()}_{recip_key}".encode("utf-8")
        if old_pending_msg_count:
            await self.redis.hincrby(
                "uid_recip_key_pending_msg_count",
                new_uid_recip_key,
                int(old_pending_msg_count.decode()),
            )
        return new_uid.decode()

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
        topic = self.config.acapy_outbound_topic
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
            recip_key = _recipients_from_packed_message(payload)
            if isinstance(payload, bytes):
                payload_dict = json.loads(payload.decode())
            else:
                payload_dict = json.loads(payload)
            direct_response_request = False
            transport_dec = payload_dict.get("~transport")
            if transport_dec:
                direct_response_mode = transport_dec.get("return_route")
                if direct_response_mode and direct_response_mode != "none":
                    direct_response_request = True
            txn_id = str(uuid4())
            if direct_response_request:
                message = str.encode(
                    json.dumps(
                        {
                            "service": {"url": endpoint},
                            "payload": base64.urlsafe_b64encode(payload).decode(),
                            "headers": headers,
                            "txn_id": txn_id,
                        }
                    ),
                )
            if await self.redis.hexists("recip_key_uid_map", recip_key):
                plugin_uid = await self.redis.hget("recip_key_uid_map", recip_key)
            else:
                plugin_uid = await self.assign_recip_key_to_uid(recip_key)
            last_accessed_map_value = await self.redis.hget(
                "uid_last_access_map", plugin_uid
            )
            stale_uid_check = False
            if not last_accessed_map_value:
                stale_uid_check = True
            elif last_accessed_map_value and (
                get_timedelta_seconds(str_to_datetime(last_accessed_map_value.decode()))
                >= 15
            ):
                stale_uid_check = True
            if stale_uid_check:
                old_uid = plugin_uid
                recip_keys_list = await self.get_recip_keys_list(old_uid)
                reassign_uid = False
                for recip_key in recip_keys_list:
                    uid_recip_key = f"{old_uid.decode()}_{recip_key}".encode("utf-8")
                    enc_uid_recip_key_msg_cnt = await self.redis.hget(
                        "uid_recip_key_pending_msg_count", uid_recip_key
                    )
                    if (
                        enc_uid_recip_key_msg_cnt is not None
                        and int(enc_uid_recip_key_msg_cnt.decode()) >= 1
                    ):
                        reassign_uid = True
                        break
                if reassign_uid:
                    for recip_key in recip_keys_list:
                        new_uid = await self.reassign_recip_key_to_uid(
                            old_uid, recip_key
                        )
                        if recip_key is recip_key:
                            plugin_uid = new_uid
                    updated_recip_keys_list = await self.get_recip_keys_list(old_uid)
                    if len(updated_recip_keys_list) == 0:
                        await self.redis.hdel(
                            "uid_recip_keys_map",
                            old_uid,
                        )
            uid_recip_key = f"{plugin_uid.decode()}_{recip_key}".encode("utf-8")
            await self.redis.hincrby(
                "uid_recip_key_pending_msg_count", uid_recip_key, 1
            )
            topic = f"{topic}_{recip_key}"
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
