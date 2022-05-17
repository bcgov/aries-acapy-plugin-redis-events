import asyncio
import aiohttp
import base64
import redis
import os
import string
import uvicorn
import json

from asynctest import TestCase as AsyncTestCase, mock as async_mock, PropertyMock
from pathlib import Path
from time import time

from .. import deliver as test_module
from ..deliver import Deliverer, MessageDeliverer, HookDeliverer, main

test_msg_a = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test"},
                "endpoint": "http://localhost:9000",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_b = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "http://localhost:9001",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_c = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "http://localhost:9002",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_d = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "http://localhost:9003",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
                "retries": 6,
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_e = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "http://localhost:9004",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
                "retry_time": int(time()),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_err_a = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_err_b = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "http://localhost:9005",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
                "retries": 6,
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_err_c = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "ws://localhost:9006",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)
test_msg_err_d = (
    None,
    str.encode(
        json.dumps(
            {
                "headers": {"content-type": "test1"},
                "endpoint": "ws://localhost:9007",
                "payload": base64.urlsafe_b64encode(
                    (string.digits + string.ascii_letters).encode(encoding="utf-8")
                ).decode(),
            }
        ),
        encoding="utf-8",
    ),
)


class TestRedisHandler(AsyncTestCase):
    async def test_main(self):
        Deliverer.running = PropertyMock(side_effect=[True, True, False])
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_delivery", autospec=True
        ), async_mock.patch.object(
            Deliverer, "process_retries", autospec=True
        ), async_mock.patch.object(
            Path, "open", async_mock.MagicMock()
        ), async_mock.patch.object(
            uvicorn, "run", async_mock.MagicMock()
        ), async_mock.patch.dict(
            os.environ,
            {
                "REDIS_SERVER": "test",
                "STATUS_ENDPOINT_HOST": "5002",
                "STATUS_ENDPOINT_PORT": "0.0.0.0",
                "STATUS_ENDPOINT_API_KEY": "test1234",
            },
        ), async_mock.patch.object(
            test_module, "start_status_endpoints_server", async_mock.MagicMock()
        ) as mock_status_endpoint:
            main([])
            mock_status_endpoint.assert_called_once()

    async def test_main_x(self):
        with self.assertRaises(SystemExit):
            main([])

        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_delivery", autospec=True
        ), async_mock.patch.object(
            Deliverer, "process_retries", autospec=True
        ), async_mock.patch.object(
            Path, "open", async_mock.MagicMock()
        ), async_mock.patch.object(
            uvicorn, "run", async_mock.MagicMock()
        ), async_mock.patch.object(
            test_module, "start_status_endpoints_server", async_mock.MagicMock()
        ) as mock_status_endpoint, async_mock.patch.dict(
            os.environ,
            {
                "REDIS_SERVER": "test",
            },
        ):
            main([])
            assert mock_status_endpoint.call_count == 0
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_delivery", autospec=True
        ), async_mock.patch.object(
            Deliverer, "process_retries", autospec=True
        ), async_mock.patch.object(
            Path, "open", async_mock.MagicMock()
        ), async_mock.patch.object(
            uvicorn, "run", async_mock.MagicMock()
        ), async_mock.patch.object(
            test_module, "start_status_endpoints_server", async_mock.MagicMock()
        ) as mock_status_endpoint, async_mock.patch.dict(
            os.environ,
            {
                "REDIS_SERVER": "test",
                "STATUS_ENDPOINT_HOST": "5002",
                "STATUS_ENDPOINT_PORT": "0.0.0.0",
            },
        ):
            main([])
            assert mock_status_endpoint.call_count == 0
        sentinel = PropertyMock(return_value=False)
        Deliverer.running = sentinel
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(
                ping=async_mock.MagicMock(side_effect=redis.exceptions.RedisError)
            ),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_delivery", autospec=True
        ), async_mock.patch.object(
            Deliverer, "process_retries", autospec=True
        ), async_mock.patch.object(
            Path, "open", async_mock.MagicMock()
        ), async_mock.patch.object(
            uvicorn, "run", async_mock.MagicMock()
        ), async_mock.patch.object(
            test_module, "start_status_endpoints_server", async_mock.MagicMock()
        ) as mock_status_endpoint, async_mock.patch.dict(
            os.environ,
            {
                "REDIS_SERVER": "test",
                "STATUS_ENDPOINT_HOST": "5002",
                "STATUS_ENDPOINT_PORT": "0.0.0.0",
                "STATUS_ENDPOINT_API_KEY": "test1234",
            },
        ):
            main([])
            assert mock_status_endpoint.call_count == 1

    async def test_process_delivery(self):
        with async_mock.patch.object(
            aiohttp.ClientSession,
            "post",
            async_mock.CoroutineMock(return_value=async_mock.MagicMock(status=200)),
        ), async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_retries", async_mock.CoroutineMock()
        ):
            Deliverer.running = PropertyMock(
                side_effect=[True, True, True, True, False]
            )
            mock_redis.blpop = async_mock.MagicMock(
                side_effect=[
                    test_msg_a,
                    test_msg_b,
                    test_msg_c,
                    test_msg_d,
                ]
            )
            mock_redis.rpush = async_mock.MagicMock()
            mock_redis.zadd = async_mock.MagicMock()
            service = MessageDeliverer(
                "test", "acapy", "test_topic", "test_retry_topic"
            )
            service.redis = mock_redis
            await service.process_delivery()

        with async_mock.patch.object(
            aiohttp.ClientSession,
            "post",
            async_mock.CoroutineMock(return_value=async_mock.MagicMock(status=200)),
        ), async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis, async_mock.patch.object(
            Deliverer, "process_retries", async_mock.CoroutineMock()
        ):
            Deliverer.running = PropertyMock(
                side_effect=[True, True, True, True, False]
            )
            mock_redis.blpop = async_mock.MagicMock(
                side_effect=[
                    test_msg_a,
                    test_msg_b,
                    test_msg_c,
                    test_msg_d,
                ]
            )
            mock_redis.rpush = async_mock.MagicMock()
            mock_redis.zadd = async_mock.MagicMock()
            service = HookDeliverer("test", "acapy", "test_topic", "test_retry_topic")
            service.redis = mock_redis
            await service.process_delivery()

    async def test_process_delivery_msg_x(self):
        with async_mock.patch.object(
            aiohttp.ClientSession,
            "post",
            async_mock.CoroutineMock(
                side_effect=[
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    async_mock.MagicMock(status=400),
                    async_mock.MagicMock(status=200),
                ]
            ),
        ), async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis:
            Deliverer.running = PropertyMock(
                side_effect=[True, True, True, True, True, False]
            )
            mock_redis.blpop = async_mock.MagicMock(
                side_effect=[
                    test_module.RedisError,
                    test_msg_a,
                    test_msg_b,
                    test_msg_d,
                    test_msg_err_a,
                    test_msg_err_b,
                ]
            )
            mock_redis.rpush = async_mock.MagicMock()
            mock_redis.zadd = async_mock.MagicMock(
                side_effect=[test_module.RedisError, None, None]
            )
            service = MessageDeliverer(
                "test", "acapy", "test_topic", "test_retry_topic"
            )
            service.redis = mock_redis
            await service.process_delivery()

    async def test_process_retries_a(self):
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis:
            Deliverer.running = PropertyMock(side_effect=[True, True, True, False])
            mock_redis.zrangebyscore = async_mock.MagicMock(
                side_effect=[
                    test_msg_e,
                    test_msg_e,
                    None,
                ]
            )
            mock_redis.zrem = async_mock.MagicMock(return_value=1)
            mock_redis.rpush = async_mock.MagicMock()
            service = MessageDeliverer(
                "test", "acapy", "test_topic", "test_retry_topic"
            )
            service.retry_timedelay_s = 0.1
            service.redis = mock_redis
            await service.process_retries()

    async def test_process_retries_b(self):
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis:
            Deliverer.running = PropertyMock(side_effect=[True, False])
            mock_redis.zrangebyscore = async_mock.MagicMock(
                side_effect=[
                    test_module.RedisError,
                    [test_msg_e, test_msg_e, test_msg_e],
                ]
            )
            mock_redis.zrem = async_mock.MagicMock(
                side_effect=[0, test_module.RedisError, test_msg_e, 0]
            )
            mock_redis.rpush = async_mock.MagicMock(
                side_effect=[test_module.RedisError, None]
            )
            service = HookDeliverer("test", "acapy", "test_topic", "test_retry_topic")
            service.retry_timedelay_s = 0.1
            service.redis = mock_redis
            await service.process_retries()

    def test_is_running(self):
        with async_mock.patch.object(
            redis.cluster.RedisCluster,
            "from_url",
            async_mock.MagicMock(),
        ) as mock_redis:
            sentinel = PropertyMock(return_value=True)
            Deliverer.running = sentinel
            service = MessageDeliverer(
                "test", "acapy", "test_topic", "test_retry_topic"
            )
            mock_redis = async_mock.MagicMock(ping=async_mock.MagicMock())
            service.redis = mock_redis
            service.running = True
            assert service.is_running()
            sentinel = PropertyMock(return_value=False)
            Deliverer.running = sentinel
            service = MessageDeliverer(
                "test", "acapy", "test_topic", "test_retry_topic"
            )
            mock_redis = async_mock.MagicMock(ping=async_mock.MagicMock())
            service.redis = mock_redis
            service.running = False
            assert not service.is_running()
            sentinel = PropertyMock(return_value=True)
            Deliverer.running = sentinel
            service = HookDeliverer("test", "acapy", "test_topic", "test_retry_topic")
            mock_redis = async_mock.MagicMock(
                ping=async_mock.MagicMock(side_effect=redis.exceptions.RedisError)
            )
            service.redis = mock_redis
            service.running = True
            assert not service.is_running()
