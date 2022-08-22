"""Testing basic kafka stuff."""
import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_round_trip(redis):
    """Test that we can get to and from Redis."""

    async def recieve_message(topic: str):
        while True:
            msg = await redis.blpop(topic, 0.2)
            if not msg:
                await asyncio.sleep(1)
                continue
            return msg[1]

    await redis.rpush(
        "test-topic",
        b"test-payload",
    )
    msg = await asyncio.wait_for(recieve_message("test-topic"), 35)
    assert msg
    assert msg == b"test-payload"
