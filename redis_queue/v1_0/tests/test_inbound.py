import asyncio
import base64
import pytest
import json
import os
import string

from aries_cloudagent.core.in_memory import InMemoryProfile
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.transport.inbound.session import InboundSession
from aries_cloudagent.transport.inbound.message import InboundMessage
from aries_cloudagent.messaging.error import MessageParseError
from aiohttp.test_utils import unused_port
from asynctest import TestCase as AsyncTestCase, mock as async_mock, PropertyMock
from redis.asyncio import RedisCluster
from redis.exceptions import RedisError


from .. import inbound as test_inbound
from ..inbound import RedisInboundTransport

SETTINGS = {
    "plugin_config": {
        "redis_queue": {
            "connection": {"connection_url": "test"},
            "inbound": {
                "acapy_inbound_topic": "acapy_inbound",
                "acapy_direct_resp_topic": "acapy_inbound_direct_resp",
            },
            "outbound": {
                "acapy_outbound_topic": "acapy_outbound",
                "mediator_mode": False,
            },
        }
    }
}

TEST_INBOUND_MSG_DIRECT_RESPONSE = str.encode(
    json.dumps(
        {
            "payload": "eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWMFppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaXdnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFFtMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00zYm10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FUkNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZDFFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazBaamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhSRlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eGF6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiIsICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4RndfVHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkdSUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVBZVFiakktVmpkN21hcWdTNElGTlEifQ==",
            "txn_id": "test1234",
            "transport_type": "http",
        }
    )
)

TEST_INBOUND_MSG_A = str.encode(
    json.dumps(
        {
            "payload": "eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWMFppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaXdnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFFtMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00zYm10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FUkNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZDFFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazBaamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhSRlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eGF6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiIsICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4RndfVHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkdSUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVBZVFiakktVmpkN21hcWdTNElGTlEifQ==",
        }
    )
)

TEST_INBOUND_MSG_B = str.encode(
    json.dumps(
        {
            "payload": "eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWMFppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaXdnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFFtMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00zYm10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FUkNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZDFFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazBaamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhSRlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eGF6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiIsICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4RndfVHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkdSUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVBZVFiakktVmpkN21hcWdTNElGTlEifQ==",
            "transport_type": "http",
        }
    )
)

TEST_INBOUND_MSG_C = str.encode(
    json.dumps(
        {
            "payload": "eyJwcm90ZWN0ZWQiOiAiZXlKbGJtTWlPaUFpZUdOb1lXTm9ZVEl3Y0c5c2VURXpNRFZmYVdWMFppSXNJQ0owZVhBaU9pQWlTbGROTHpFdU1DSXNJQ0poYkdjaU9pQWlRWFYwYUdOeWVYQjBJaXdnSW5KbFkybHdhV1Z1ZEhNaU9pQmJleUpsYm1OeWVYQjBaV1JmYTJWNUlqb2dJakZqWjNsMFFtMTNNM0V4YUdkaVZ6Qkpiak50U0c4MldXaExUMnRwUnpWRWVUaHJSakpJV2pZeGNUSnZXV00zYm10dVN6bE9TVWMyU0VobFUyTm9lV0VpTENBaWFHVmhaR1Z5SWpvZ2V5SnJhV1FpT2lBaU5FUkNTalJhY0RnMU1XZHFlazUwU20xdGIwVTVOMWR4Vm5KWFRqTTJlVnBTWVVkcFpqUkJSM0o0ZDFFaUxDQWljMlZ1WkdWeUlqb2dJak5XY0hsU2NVRlpUV3N5Tms1RmMwUXpObU5mWjJnMFZIazBaamd3TUd4RFJHRXdNMWxsUlc1bVJYQm1WMmhKTFdkelpFY3RWR1JrTVdWTmFEbFpTWG8zTkhSRlN6SnNSMVZhVFhwZk5HdDFkMEpUVWtvMFRGOWhkMVJLUVZWVmQydFRWbmhyTXpSblVWVmZOV2RyZDFSa09FWTFUa0ZsU1U1UVZTSXNJQ0pwZGlJNklDSnFWVkpDUW1OaVQzZzNOa05zVmw4eGF6aFJNMjlyVW5KdFJHUTFhM0JwUWlKOWZWMTkiLCAiaXYiOiAiTVdnR3VRNF9ab2dxVVJUbiIsICJjaXBoZXJ0ZXh0IjogIlVNTGFQOU13ZF9wOFR1bWdwcVZWQWZTSWZXc1g3a0lWLUR4RndfVHRTQ2pWdTVTbG5RYmtkTVJLd3VyZGI1dmd6Q0tUNUFybFV0WEFMMm1sSUlpUGpSYzVmSzhLc013S0dFemkycEtrdmxDN1EzUXRKWTE5WmVTSjlYMGlUOWxOamNEM25KS0o1bzlkSjhVWGZpNU80ZEtaLWxlVy1qOHlzTEFTSTh1eEZYVVNoUmxlNy03bm5HZkZnRlZBRjNaWVpqNlRXUUJrdkdSUk96TzMwTHNEWHBzalNqMWZfd056RWdxTmpPMERZemRKa0lBNm1BQ1AiLCAidGFnIjogImVBZVFiakktVmpkN21hcWdTNElGTlEifQ==",
            "transport_type": "ws",
        }
    )
)

TEST_INBOUND_INVALID = b"""{
    "payload" "==",
    "transport_type": "ws",
}"""


class TestRedisInbound(AsyncTestCase):
    def setUp(self):
        self.port = unused_port()
        self.session = None
        self.profile = InMemoryProfile.test_profile()

    async def test_init(self):
        self.profile.context.injector.bind_instance(
            RedisCluster, async_mock.MagicMock()
        )
        RedisInboundTransport.running = PropertyMock(
            side_effect=[True, True, True, False]
        )
        redis_inbound_inst = RedisInboundTransport(
            "0.0.0.0",
            self.port,
            async_mock.CoroutineMock(
                return_value=async_mock.MagicMock(
                    receive=async_mock.CoroutineMock(),
                    wait_response=async_mock.CoroutineMock(
                        side_effect=[
                            b"test_response_1",
                            "test_response_2",
                            MessageParseError,
                        ]
                    ),
                    profile=async_mock.MagicMock(
                        settings={"emit_new_didcomm_mime_type": True}
                    ),
                )
            ),
            root_profile=self.profile,
        )

        assert redis_inbound_inst

    async def test_start(self):
        self.profile.settings["emit_new_didcomm_mime_type"] = False
        self.profile.context.injector.bind_instance(
            RedisCluster,
            async_mock.MagicMock(
                hset=async_mock.CoroutineMock(),
                hget=async_mock.CoroutineMock(
                    side_effect=[
                        base64.urlsafe_b64encode(
                            json.dumps(
                                [
                                    "test_recip_key_1",
                                    "test_recip_key_2",
                                    "test_recip_key_3",
                                    "test_recip_key_5",
                                ]
                            ).encode("utf-8")
                        ).decode(),
                        b"1",
                        b"2",
                        b"1",
                        base64.urlsafe_b64encode(
                            json.dumps(
                                [
                                    "test_recip_key_1",
                                    "test_recip_key_2",
                                    "test_recip_key_4",
                                    "test_recip_key_3",
                                    "test_recip_key_5",
                                ]
                            ).encode("utf-8")
                        ).decode(),
                        b"1",
                        b"1",
                        b"2",
                        b"3",
                        None,
                    ]
                ),
                blpop=async_mock.CoroutineMock(
                    side_effect=[
                        (None, TEST_INBOUND_MSG_DIRECT_RESPONSE),
                        (None, TEST_INBOUND_MSG_A),
                        (None, TEST_INBOUND_MSG_B),
                        (None, TEST_INBOUND_INVALID),
                        (None, TEST_INBOUND_MSG_DIRECT_RESPONSE),
                        None,
                        (None, TEST_INBOUND_MSG_B),
                        (None, TEST_INBOUND_MSG_C),
                        (None, TEST_INBOUND_MSG_DIRECT_RESPONSE),
                    ]
                ),
                rpush=async_mock.CoroutineMock(side_effect=[RedisError, None]),
            ),
        )
        with async_mock.patch.object(
            test_inbound.asyncio, "sleep", async_mock.CoroutineMock()
        ):
            RedisInboundTransport.running = PropertyMock(
                side_effect=[
                    True,
                    True,
                    True,
                    False,
                ]
            )
            redis_inbound_inst = RedisInboundTransport(
                "0.0.0.0",
                self.port,
                async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(
                        receive=async_mock.CoroutineMock(),
                        wait_response=async_mock.CoroutineMock(
                            side_effect=[
                                b"test_response_1",
                                "test_response_2",
                                MessageParseError,
                            ]
                        ),
                        profile=self.profile,
                    )
                ),
                root_profile=self.profile,
            )

            await redis_inbound_inst.start()
            await redis_inbound_inst.stop()

    async def test_start_x(self):
        self.profile.settings["emit_new_didcomm_mime_type"] = True
        self.profile.context.injector.bind_instance(
            RedisCluster,
            async_mock.MagicMock(
                hset=async_mock.CoroutineMock(),
                hget=async_mock.CoroutineMock(
                    side_effect=[
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                        base64.urlsafe_b64encode(
                            json.dumps(
                                [
                                    "test_recip_key_1",
                                    "test_recip_key_2",
                                ]
                            ).encode("utf-8")
                        ).decode(),
                        b"1",
                    ]
                ),
                blpop=async_mock.CoroutineMock(
                    side_effect=[
                        (None, TEST_INBOUND_MSG_DIRECT_RESPONSE),
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                        RedisError,
                    ]
                ),
                rpush=async_mock.CoroutineMock(),
            ),
        )
        with async_mock.patch.object(
            test_inbound.asyncio, "sleep", async_mock.CoroutineMock()
        ):
            RedisInboundTransport.running = PropertyMock(
                side_effect=[
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    False,
                ]
            )
            redis_inbound_inst = RedisInboundTransport(
                "0.0.0.0",
                self.port,
                async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(
                        receive=async_mock.CoroutineMock(),
                        wait_response=async_mock.CoroutineMock(
                            side_effect=[
                                b"test_response_1",
                            ]
                        ),
                        profile=self.profile,
                    )
                ),
                root_profile=self.profile,
            )
            with self.assertRaises(test_inbound.InboundTransportError):
                await redis_inbound_inst.start()
                await redis_inbound_inst.stop()
