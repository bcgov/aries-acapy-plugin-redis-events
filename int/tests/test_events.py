"""Basic Message Tests"""
import asyncio
import json
import pytest

from acapy_client import Client
from acapy_client.api.basicmessage import send_basicmessage
from acapy_client.models.send_message import SendMessage
from acapy_client.models import ConnectionStaticResult
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo

PAYLOAD_B64 = """
    eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWM
    FppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaX
    dnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFF
    tMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00z
    Ym10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FU
    kNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZD
    FFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazB
    aamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhS
    RlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV
    2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eG
    F6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiI
    sICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4Rndf
    VHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc
    013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU
    80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkd
    SUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVB
    ZVFiakktVmpkN21hcWdTNElGTlEifQ==
"""


@pytest.mark.asyncio
async def test_event_pushed_to_redis(
    agent_connection: ConnectionStaticResult, echo: EchoClient, suite_seed: str, redis
):
    conn = await echo.new_connection(
        seed=suite_seed,
        endpoint=agent_connection.my_endpoint,
        their_vk=agent_connection.my_verkey,
    )
    assert conn
    assert await redis.blpop("acapy-record-base", 10)
    assert await redis.blpop("acapy-record-with-state-base", 10)
    # await echo.send_message(
    #     conn,
    #     {
    #         "@type": "https://didcomm.org/basicmessage/1.0/message",
    #         "content": "Your hovercraft is full of eels.",
    #     },
    # )
    # assert await redis.blpop("acapy-basicmessage-received", 10)


@pytest.mark.asyncio
async def test_outbound_queue(backchannel: Client, connection_id: str, redis):
    await send_basicmessage.asyncio(
        client=backchannel,
        conn_id=connection_id,
        json_body=SendMessage(content="test"),
    )
    msg = await redis.blpop("acapy_outbound", 30)
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
    await asyncio.sleep(5)
    message = await echo.get_message(connection)
    assert message["content"] == "test"


@pytest.mark.asyncio
async def test_deliverer_retry_on_failure(
    backchannel: Client,
    connection_id: str,
    redis,
):
    outbound_msg = {
        "service": {"url": "http://echo:3002/fake/"},
        "payload": PAYLOAD_B64,
    }
    # produce a outbound message with bad enpoint
    await redis.rpush(
        "acapy_outbound",
        str.encode(json.dumps(outbound_msg)),
    )
    # assume failure code 400, delay queue, and failure code 400 ...
    await asyncio.sleep(15)
    msg = await redis.blpop("acapy_outbound", 15)
    assert msg
    # check for manual commit of previous message by handling a new message
    await send_basicmessage.asyncio(
        client=backchannel,
        conn_id=connection_id,
        json_body=SendMessage(content="test2"),
    )
    msg = await redis.blpop("acapy_outbound", 30)
    assert msg
