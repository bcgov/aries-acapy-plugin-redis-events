"""Basic Message Tests"""
import asyncio
import json

import pytest
from acapy_client import Client
from acapy_client.api.basicmessage import send_basicmessage
from acapy_client.models.send_message import SendMessage
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo


@pytest.mark.asyncio
async def test_event_pushed_to_redis(
    connection: ConnectionInfo, echo: EchoClient, redis
):
    async def recieve_message(topic: str):
        while True:
            msg = await redis.blpop(topic, 0.2)
            if not msg:
                await asyncio.sleep(1)
                continue
            return msg[1]

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/basicmessage/1.0/message",
            "content": "Your hovercraft is full of eels.",
        },
    )
    msg = await asyncio.wait_for(recieve_message("acapy_outbound"), 5)
    assert msg


@pytest.mark.asyncio
async def test_outbound_queue(backchannel: Client, connection_id: str, redis):
    async def recieve_message(topic: str):
        while True:
            msg = await redis.blpop(topic, 0.2)
            if not msg:
                await asyncio.sleep(1)
                continue
            return msg[1]

    await send_basicmessage.asyncio(
        client=backchannel,
        conn_id=connection_id,
        json_body=SendMessage(content="test"),
    )
    msg = await asyncio.wait_for(recieve_message("acapy_outbound"), 5)
    assert msg


@pytest.mark.asyncio
async def test_deliverer(
    backchannel: Client,
    connection_id: str,
    echo: EchoClient,
    connection: ConnectionInfo,
):
    await send_basicmessage.asyncio(
        client=backchannel,
        conn_id=connection_id,
        json_body=SendMessage(content="test"),
    )
    await asyncio.sleep(1)
    message = await echo.get_message(connection)
    assert message["content"] == "test"


@pytest.mark.asyncio
async def test_deliverer_retry_on_failure(
    redis,
    backchannel: Client,
    connection_id: str,
):
    async def recieve_message(topic: str):
        while True:
            msg = await redis.blpop(topic, 0.2)
            if not msg:
                await asyncio.sleep(1)
                continue
            return msg[1]

    outbound_msg = {
        "service": {"url": "http://echo:3002/fake/"},
        "payload": "eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWMFppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaXdnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFFtMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00zYm10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FUkNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZDFFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazBaamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhSRlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eGF6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiIsICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4RndfVHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkdSUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVBZVFiakktVmpkN21hcWdTNElGTlEifQ==",
    }
    # produce a outbound message with bad enpoint
    await redis.rpush(
        "acapy_outbound_retry",
        str.encode(json.dumps(outbound_msg, indent=2), encoding="utf8"),
    )
    # assume failure code 400, delay queue, and failure code 400 ...
    msg = await asyncio.wait_for(recieve_message("acapy_outbound_retry"), 35)
    assert msg
    # check for manual commit of previous message by handling a new message
    await send_basicmessage.asyncio(
        client=backchannel,
        conn_id=connection_id,
        json_body=SendMessage(content="test2"),
    )
    msg = await asyncio.wait_for(recieve_message("acapy_outbound"), 5)
    assert msg
