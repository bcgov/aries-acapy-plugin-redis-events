import asyncio
import logging
import base64
import sys
import json

from aiohttp import WSMessage, WSMsgType, web
from redis.cluster import RedisCluster as Redis
from redis.exceptions import RedisError
from os import getenv
from uuid import uuid4

from ..status_endpoints import start_status_endpoints_server

logging.basicConfig(
    format="%(asctime)s | %(levelname)s: %(message)s",
    level=logging.INFO,
)


class WSRelay:
    """Inbound WS delivery relay."""

    running = False
    ready = False

    def __init__(
        self,
        host: str,
        prefix: str,
        site_host: str,
        site_port: str,
        direct_resp_topic: str,
        inbound_topic: str,
    ):
        """Initialize Relay."""
        self._host = host
        self.prefix = prefix
        self.site_host = site_host
        self.site_port = site_port
        self.redis = Redis.from_url(self._host)
        self.direct_response_txn_request_map = {}
        self.direct_resp_topic = direct_resp_topic
        self.inbound_topic = inbound_topic
        self.site = None
        self.timedelay_s = 1

    async def run(self):
        """Run the service."""
        try:
            self.redis.ping()
            self.ready = True
            self.running = True
            await asyncio.gather(self.start(), self.process_direct_responses())
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

    async def start(self):
        """Construct the aiohttp application."""
        app = web.Application()
        app.add_routes([web.get("/", self.message_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, host=self.site_host, port=self.site_port)
        await self.site.start()

    async def stop(self) -> None:
        """Shutdown."""
        if self.site:
            await self.site.stop()
            self.site = None

    async def process_direct_responses(self):
        """Process inbound_direct_responses and update direct_response_txn_request_map."""
        while self.running:
            msg_received = False
            while not msg_received:
                try:
                    msg = self.redis.blpop(self.direct_resp_topic, 0.2)
                    msg_received = True
                except RedisError as err:
                    await asyncio.sleep(1)
                    logging.exception(f"Unexpected redis client exception: {str(err)}")
            if not msg:
                await asyncio.sleep(1)
                continue
            msg = json.loads(msg[1].decode("utf8"))
            if not isinstance(msg, dict):
                logging.error("Received non-dict message")
                continue
            elif "response_data" not in msg:
                logging.error("No response provided")
                continue
            elif "txn_id" not in msg:
                logging.error("No txn_id provided")
                continue
            txn_id = msg["txn_id"]
            response_data = msg["response_data"]
            self.direct_response_txn_request_map[txn_id] = response_data
            await asyncio.sleep(self.timedelay_s)

    async def get_direct_responses(self, txn_id):
        """Get direct_response for a specific transaction/request."""
        while self.running:
            if txn_id in self.direct_response_txn_request_map:
                return self.direct_response_txn_request_map[txn_id]
            await asyncio.sleep(self.timedelay_s)

    async def message_handler(self, request):
        """Message handler for inbound messages."""
        ws = web.WebSocketResponse(
            autoping=True,
            heartbeat=3,
            receive_timeout=15,
        )
        await ws.prepare(request)
        loop = asyncio.get_event_loop()
        inbound = loop.create_task(ws.receive())
        while not ws.closed:
            await asyncio.wait((inbound), return_when=asyncio.FIRST_COMPLETED)
            if inbound.done():
                msg: WSMessage = inbound.result()
                if msg.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                    message_dict = json.loads(msg.data)
                    direct_response_request = False
                    transport_dec = message_dict.get("~transport")
                    if transport_dec:
                        direct_response_mode = transport_dec.get("return_route")
                        if direct_response_mode and direct_response_mode != "none":
                            direct_response_request = True
                    txn_id = str(uuid4())
                    if direct_response_request:
                        self.direct_response_txn_request_map[txn_id] = request
                        message = str.encode(
                            json.dumps(
                                {
                                    "payload": base64.urlsafe_b64encode(
                                        msg.data
                                    ).decode(),
                                    "txn_id": txn_id,
                                    "transport_type": "ws",
                                }
                            )
                        )
                        response_sent = False
                        while not response_sent:
                            try:
                                self.redis.rpush(self.inbound_topic, message)
                                response_sent = True
                            except RedisError as err:
                                await asyncio.sleep(1)
                                logging.exception(
                                    f"Unexpected redis client exception: {str(err)}"
                                )
                        try:
                            response_data = await asyncio.wait_for(
                                self.get_direct_responses(
                                    txn_id=txn_id,
                                ),
                                15,
                            )
                            response = response_data["response"]
                            if response:
                                if isinstance(response, bytes):
                                    await ws.send_bytes(response)
                                else:
                                    await ws.send_str(response)
                        except asyncio.TimeoutError:
                            pass
                    else:
                        logging.info(f"Message received from {request.remote}")
                        message = str.encode(
                            json.dumps(
                                {
                                    "payload": base64.urlsafe_b64encode(
                                        msg.data
                                    ).decode(),
                                    "transport_type": "ws",
                                }
                            )
                        )
                        msg_sent = False
                        while not msg_sent:
                            try:
                                self.redis.rpush(self.inbound_topic, message)
                                msg_sent = True
                            except RedisError as err:
                                await asyncio.sleep(1)
                                logging.exception(
                                    f"Unexpected redis client exception: {str(err)}"
                                )
                elif msg.type == WSMsgType.ERROR:
                    logging.error(
                        "Websocket connection closed with exception: %s",
                        ws.exception(),
                    )
                else:
                    logging.error(
                        "Unexpected Websocket message type received: %s: %s, %s",
                        msg.type,
                        msg.data,
                        msg.extra,
                    )
                if not ws.closed:
                    inbound = loop.create_task(ws.receive())
        if inbound and not inbound.done():
            inbound.cancel()
        if not ws.closed:
            await ws.close()
        logging.error("Websocket connection closed")
        return ws


class HttpRelay:
    """Inbound HTTP delivery service."""

    running = False
    ready = False

    def __init__(
        self,
        host: str,
        prefix: str,
        site_host: str,
        site_port: str,
        direct_resp_topic: str,
        inbound_topic: str,
    ):
        """Initialize KafkaHTTPHandler."""
        self._host = host
        self.prefix = prefix
        self.site_host = site_host
        self.site_port = site_port
        self.redis = Redis.from_url(self._host)
        self.direct_response_txn_request_map = {}
        self.direct_resp_topic = direct_resp_topic
        self.inbound_topic = inbound_topic
        self.site = None
        self.timedelay_s = 1

    async def run(self):
        """Run the service."""
        try:
            self.redis.ping()
            self.ready = True
            self.running = True
            await asyncio.gather(self.start(), self.process_direct_responses())
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

    async def start(self):
        """Construct the aiohttp application."""
        app = web.Application()
        app.add_routes([web.get("/", self.invite_handler)])
        app.add_routes([web.post("/", self.message_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, host=self.site_host, port=self.site_port)
        await self.site.start()

    async def stop(self) -> None:
        """Shutdown."""
        if self.site:
            await self.site.stop()
            self.site = None

    async def process_direct_responses(self):
        """Process inbound_direct_responses and update direct_response_txn_request_map."""
        while self.running:
            msg_received = False
            while not msg_received:
                try:
                    msg = self.redis.blpop(self.direct_resp_topic, 0.2)
                    msg_received = True
                except RedisError as err:
                    await asyncio.sleep(1)
                    logging.exception(f"Unexpected redis client exception: {str(err)}")
            if not msg:
                await asyncio.sleep(1)
                continue
            msg = json.loads(msg[1].decode("utf8"))
            if not isinstance(msg, dict):
                logging.error("Received non-dict message")
                continue
            elif "response_data" not in msg:
                logging.error("No response provided")
                continue
            elif "txn_id" not in msg:
                logging.error("No txn_id provided")
                continue
            txn_id = msg["txn_id"]
            response_data = msg["response_data"]
            self.direct_response_txn_request_map[txn_id] = response_data
            await asyncio.sleep(self.timedelay_s)

    async def get_direct_responses(self, txn_id):
        """Get direct_response for a specific transaction/request."""
        while self.running:
            if txn_id in self.direct_response_txn_request_map:
                return self.direct_response_txn_request_map[txn_id]
            await asyncio.sleep(self.timedelay_s)

    async def invite_handler(self, request):
        """Handle inbound invitation."""
        if request.query.get("c_i"):
            return web.Response(
                text="You have received a connection invitation. To accept the "
                "invitation, paste it into your agent application."
            )
        else:
            return web.Response(status=200)

    async def message_handler(self, request):
        """Message handler for inbound messages."""
        ctype = request.headers.get("content-type", "")
        if ctype.split(";", 1)[0].lower() == "application/json":
            body = await request.text()
        else:
            body = await request.read()
        message_dict = json.loads(body)
        direct_response_request = False
        transport_dec = message_dict.get("~transport")
        if transport_dec:
            direct_response_mode = transport_dec.get("return_route")
            if direct_response_mode and direct_response_mode != "none":
                direct_response_request = True
        txn_id = str(uuid4())
        if direct_response_request:
            self.direct_response_txn_request_map[txn_id] = request
            message = str.encode(
                json.dumps(
                    {
                        "payload": base64.urlsafe_b64encode(body).decode(),
                        "txn_id": txn_id,
                        "transport_type": "http",
                    }
                )
            )
            response_sent = False
            while not response_sent:
                try:
                    self.redis.rpush(self.inbound_topic, message)
                    response_sent = True
                except RedisError as err:
                    await asyncio.sleep(1)
                    logging.exception(f"Unexpected redis client exception: {str(err)}")
            try:
                response_data = await asyncio.wait_for(
                    self.get_direct_responses(
                        txn_id=txn_id,
                    ),
                    15,
                )
                response = response_data["response"]
                content_type = (
                    response_data["content_type"]
                    if "content_type" in response_data
                    else "application/json"
                )
                if response:
                    return web.Response(
                        text=response,
                        status=200,
                        headers={"Content-Type": content_type},
                    )
            except asyncio.TimeoutError:
                return web.Response(status=200)
        else:
            logging.info(f"Message received from {request.remote}")
            message = str.encode(
                json.dumps(
                    {
                        "payload": base64.urlsafe_b64encode(body).decode(),
                        "transport_type": "http",
                    }
                )
            )
            msg_sent = False
            while not msg_sent:
                try:
                    self.redis.rpush(self.inbound_topic, message)
                    msg_sent = True
                except RedisError as err:
                    await asyncio.sleep(1)
                    logging.exception(f"Unexpected redis client exception: {str(err)}")
            return web.Response(status=200)


def main(args):
    """Start services."""
    REDIS_SERVER = getenv("REDIS_SERVER")
    TOPIC_PREFIX = getenv("TOPIC_PREFIX", "acapy")
    STATUS_ENDPOINT_TRANSPORT = getenv("STATUS_ENDPOINT_TRANSPORT")
    STATUS_ENDPOINT_API_KEY = getenv("STATUS_ENDPOINT_API_KEY")
    TRANSPORT_CONFIG = getenv("TRANSPORT_CONFIG")
    inbound_queue_transports = TRANSPORT_CONFIG
    if REDIS_SERVER:
        host = REDIS_SERVER
    else:
        raise SystemExit("No Redis host/connection provided.")
    prefix = TOPIC_PREFIX
    if STATUS_ENDPOINT_TRANSPORT:
        delivery_Service_endpoint_transport = STATUS_ENDPOINT_TRANSPORT
    else:
        raise SystemExit("No Delivery Service api config provided.")
    if STATUS_ENDPOINT_API_KEY:
        delivery_Service_api_key = STATUS_ENDPOINT_API_KEY
    else:
        raise SystemExit("No Delivery Service api key provided.")
    INBOUND_MSG_TOPIC = f"{prefix}-inbound-message"
    INBOUND_MSG_DIRECT_RESP = f"{prefix}-inbound-direct-response"
    api_host, api_port = delivery_Service_endpoint_transport
    handlers = []
    for inbound_transport in inbound_queue_transports:
        transport_type, site_host, site_port = inbound_transport
        if transport_type == "ws":
            logging.info(
                "Starting Redis ws inbound delivery service agent "
                f"with args: {host}, {prefix}, {site_host}, {site_port}"
            )
            handler = WSRelay(
                host,
                prefix,
                site_host,
                site_port,
                INBOUND_MSG_DIRECT_RESP,
                INBOUND_MSG_TOPIC,
            )
            handlers.append(handler)
        elif transport_type == "http":
            logging.info(
                "Starting Redis http inbound delivery service agent "
                f"with args: {host}, {prefix}, {site_host}, {site_port}"
            )
            handler = HttpRelay(
                host,
                prefix,
                site_host,
                site_port,
                INBOUND_MSG_DIRECT_RESP,
                INBOUND_MSG_TOPIC,
            )
            handlers.append(handler)
        else:
            raise SystemExit("Only ws and http transport type are supported.")
        asyncio.ensure_future(handler.run())
    start_status_endpoints_server(
        api_host, api_port, delivery_Service_api_key, handlers
    )


if __name__ == "__main__":
    main(sys.argv[1:])
