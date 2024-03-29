import base64
import json
from urllib.parse import urlparse

from pydantic import BaseModel, PrivateAttr, validator


class NoneDefaultModel(BaseModel):
    @validator("*", pre=True)
    def not_none(cls, v, field):
        if all(
            (
                # Cater for the occasion where field.default in (0, False)
                getattr(field, "default", None) is not None,
                v is None,
            )
        ):
            return field.default
        else:
            return v


class RedisQueuePayload(NoneDefaultModel):
    class Config:
        json_encoders = {bytes: lambda v: base64.urlsafe_b64encode(v).decode()}

    @classmethod
    def from_bytes(cls, value: bytes):
        payload = json.loads(value.decode("utf8"))
        return cls(**payload)

    def to_bytes(self) -> bytes:
        return str.encode(self.json(), encoding="utf8")


class Service(BaseModel):
    url: str


class OutboundPayload(RedisQueuePayload):
    service: Service
    payload: bytes
    headers: dict = {}
    retries: int = 0
    _endpoint_scheme: str = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._endpoint_scheme = urlparse(self.service.url).scheme

    @validator("payload", pre=True)
    @classmethod
    def decode_payload_to_bytes(cls, v):
        assert isinstance(v, str)
        return base64.urlsafe_b64decode(v)

    @property
    def endpoint_scheme(self):
        return self._endpoint_scheme
