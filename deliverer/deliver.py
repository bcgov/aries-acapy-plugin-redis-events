"""Redis Outbound Delivery Service."""
import aiohttp
import asyncio
import base64
import logging
import sys
import urllib
import json

from redis.cluster import RedisCluster as Redis
from redis.exceptions import RedisError
from time import time
from os import getenv

from status_endpoint.status_endpoints import start_status_endpoints_server

from . import OutboundPayload

logging.basicConfig(
    format="%(asctime)s | %(levelname)s: %(message)s",
    level=logging.INFO,
)


class Deliverer:
    """Outbound http delivery handler."""

    running = False
    ready = False

    def __init__(self, host: str, prefix: str, topic: str, retry_topic: str):
        """Initialize RedisHandler."""
        self._host = host
        self.prefix = prefix
        self.retry_interval = 5
        self.retry_backoff = 0.25
        self.outbound_topic = topic
        self.retry_topic = retry_topic
        self.redis = Redis.from_url(self._host)
        self.retry_timedelay_s = 1

    async def run(self):
        """Run the service."""
        try:
            self.redis.ping()
            self.ready = True
            self.running = True
            await asyncio.gather(self.process_delivery(), self.process_retries())
        except RedisError:
            self.ready = False
            self.running = False

    def is_running(self) -> bool:
        """Check if delivery service agent is running properly."""
        try:
            self.redis.ping()
            if self.running:
                return True
            else:
                return False
        except RedisError:
            return False

    async def process_delivery(self):
        """Process delivery."""
        client_session = aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(), trust_env=True
        )
        try:
            while self.running:
                msg_received = False
                while not msg_received:
                    try:
                        msg = self.redis.blpop(self.outbound_topic, 0.2)
                        msg_received = True
                    except RedisError as err:
                        await asyncio.sleep(1)
                        logging.exception(
                            f"Unexpected redis client exception (blpop): {str(err)}"
                        )
                if not msg:
                    await asyncio.sleep(1)
                    continue
                msg = OutboundPayload.from_bytes(msg[1])
                headers = msg.headers
                for hname, hval in headers.items():
                    if isinstance(hval, bytes):
                        hval = hval.decode("utf-8")
                    headers[hname.decode("utf-8")] = hval
                endpoint = msg.service.url
                payload = msg.payload
                parsed = urllib.parse.urlparse(endpoint)
                if parsed.scheme == "http" or parsed.scheme == "https":
                    logging.info(f"Dispatch message to {endpoint}")
                    failed = False
                    try:
                        response = await http_client.post(
                            endpoint, data=payload, headers=headers, timeout=10
                        )
                    except aiohttp.ClientError:
                        failed = True
                    except asyncio.TimeoutError:
                        failed = True
                    else:
                        if response.status < 200 or response.status >= 300:
                            logging.error("Invalid response code:", response.status)
                            failed = True
                    if failed:
                        logging.exception(f"Delivery failed for {endpoint}")
                        retries = msg.get(b"retries") or 0
                        if retries < 5:
                            await self.add_retry(
                                {
                                    "service": {"url": endpoint},
                                    "headers": headers,
                                    "payload": payload,
                                    "retries": retries + 1,
                                }
                            )
                        else:
                            logging.error(f"Exceeded max retries for {str(endpoint)}")
                elif parsed.scheme == "ws":
                    async with self.client_session.ws_connect(
                        endpoint, headers=headers
                    ) as ws:
                        if isinstance(payload, bytes):
                            await ws.send_bytes(payload)
                        else:
                            await ws.send_str(payload)
                else:
                    logging.error(f"Unsupported scheme: {parsed.scheme}")
        finally:
            await client_session.close()

    async def add_retry(self, message: dict):
        """Add undelivered message for future retries."""
        zadd_sent = False
        while not zadd_sent:
            try:
                wait_interval = pow(
                    self.retry_interval,
                    1 + (self.retry_backoff * (message["retries"] - 1)),
                )
                retry_time = int(time() + wait_interval)
                retry_msg = str.encode(
                    json.dumps(message),
                )
                self.redis.zadd(
                    f"{self.prefix}.outbound_retry",
                    {retry_msg: retry_time},
                )
                zadd_sent = True
            except RedisError as err:
                await asyncio.sleep(1)
                logging.exception(
                    f"Unexpected redis client exception (zadd): {str(err)}"
                )

    async def process_retries(self):
        """Process retries."""
        while self.running:
            zrangebyscore_rec = False
            while not zrangebyscore_rec:
                max_score = int(time())
                try:
                    rows = self.redis.zrangebyscore(
                        name=self.retry_topic,
                        min=0,
                        max=max_score,
                        start=0,
                        num=10,
                    )
                    zrangebyscore_rec = True
                except RedisError as err:
                    await asyncio.sleep(1)
                    logging.exception(
                        f"Unexpected redis client exception (zrangebyscore): {str(err)}"
                    )
            if rows:
                for message in rows:
                    zrem_rec = False
                    while not zrem_rec:
                        try:
                            count = self.redis.zrem(
                                self.retry_topic,
                                message,
                            )
                            zrem_rec = True
                        except RedisError as err:
                            await asyncio.sleep(1)
                            logging.exception(
                                f"Unexpected redis client exception (zrem): {str(err)}"
                            )
                    if count == 0:
                        # message removed by another process
                        continue
                    msg_sent = False
                    while not msg_sent:
                        try:
                            self.redis.rpush(self.outbound_topic, message)
                            msg_sent = True
                        except RedisError as err:
                            await asyncio.sleep(1)
                            logging.exception(
                                f"Unexpected redis client exception (rpush): {str(err)}"
                            )
            else:
                await asyncio.sleep(self.retry_timedelay_s)


class MessageDeliverer(Deliverer):
    """Outbound Message Http and WS Deliverer."""


class HookDeliverer(Deliverer):
    """ACA-Py Hook Http and WS deliverer."""


def main(args):
    """Start services."""
    REDIS_SERVER = getenv("REDIS_SERVER")
    TOPIC_PREFIX = getenv("TOPIC_PREFIX", "acapy")
    STATUS_ENDPOINT_HOST = getenv("STATUS_ENDPOINT_HOST")
    STATUS_ENDPOINT_PORT = getenv("STATUS_ENDPOINT_PORT")
    STATUS_ENDPOINT_API_KEY = getenv("STATUS_ENDPOINT_API_KEY")
    if REDIS_SERVER:
        host = REDIS_SERVER
    else:
        raise SystemExit("No Redis host/connection provided.")
    prefix = TOPIC_PREFIX
    OUTBOUND_MSG_TOPIC = f"{prefix}-outbound-message"
    OUTBOUND_MSG_RETRY_TOPIC = f"{prefix}-outbound-retry-message"
    HOOKS_TOPIC = f"{prefix}-outbound-webhook"
    HOOKS_RETRY_TOPIC = f"{prefix}-outbound-retry-webhook"
    msg_handler = MessageDeliverer(
        host, prefix, OUTBOUND_MSG_TOPIC, OUTBOUND_MSG_RETRY_TOPIC
    )
    msg_handler.client_session = aiohttp.ClientSession(
        cookie_jar=aiohttp.DummyCookieJar(), trust_env=True
    )
    logging.info(
        "Starting Redis outbound message delivery agent with args: "
        f"{host}, {prefix}, {OUTBOUND_MSG_TOPIC}, {OUTBOUND_MSG_RETRY_TOPIC}"
    )
    asyncio.ensure_future(msg_handler.run())
    hook_handler = HookDeliverer(host, prefix, HOOKS_TOPIC, HOOKS_RETRY_TOPIC)
    logging.info(
        "Starting Redis outbound webhook delivery agent with args: "
        f"{host}, {prefix}, {HOOKS_TOPIC}, {HOOKS_RETRY_TOPIC}"
    )
    asyncio.ensure_future(hook_handler.run())
    if STATUS_ENDPOINT_HOST and STATUS_ENDPOINT_PORT and STATUS_ENDPOINT_API_KEY:
        start_status_endpoints_server(
            STATUS_ENDPOINT_HOST,
            STATUS_ENDPOINT_PORT,
            STATUS_ENDPOINT_API_KEY,
            [msg_handler, hook_handler],
        )


if __name__ == "__main__":
    main(sys.argv[1:])
