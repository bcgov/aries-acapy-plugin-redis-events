"""Redis Queue configuration."""

import logging
from multiprocessing import connection
from typing import Any, List, Mapping, Optional, Union
from pydantic import BaseModel, Extra


LOGGER = logging.getLogger(__name__)


def _alias_generator(key: str) -> str:
    return key.replace("_", "-")


class ConnectionConfig(BaseModel):
    connection_url: str

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(connection_url="redis://default:test1234@172.28.0.103:6379")

class EventsConfig(BaseModel):
    topic_maps: Mapping[str, str]

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(
            topic_maps={
                "^acapy::webhook::(.*)$": "acapy-webhook-$wallet_id",
                "^acapy::record::([^:]*)::([^:]*)$": "acapy-record-with-state-$wallet_id",
                "^acapy::record::([^:])?": "acapy-record-$wallet_id",
                "acapy::basicmessage::received": "acapy-basicmessage-received",
            },
        )


class InboundConfig(BaseModel):
    acapy_inbound_topic: str
    acapy_direct_resp_topic: str

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(
            acapy_inbound_topic="acapy-inbound-message",
            acapy_direct_resp_topic="acapy-inbound-direct-resp",
        )


class OutboundConfig(BaseModel):
    acapy_outbound_topic: str
    mediator_mode: bool

    @classmethod
    def default(cls):
        return cls(
            acapy_outbound_topic="acapy-outbound",
            mediator_mode=False,
        )

class RedisConfig(BaseModel):
    events: Optional[EventsConfig]
    inbound: Optional[InboundConfig]
    outbound: Optional[OutboundConfig]
    connection: ConnectionConfig

    @classmethod
    def default(cls):
        return cls(
            events=EventsConfig.default(),
            inbound=InboundConfig.default(),
            outbound=OutboundConfig.default(),
            connection=ConnectionConfig.default(),
        )


def process_config_dict(config_dict: dict) -> dict:
    """Add connection to inbound, outbound, events and return updated config."""
    filter = ["inbound", "event", "outbound", "connection"]
    for key, value in config_dict.items():
        if key in filter:
            config_dict[key] = value
    return config_dict


def get_config(settings: Mapping[str, Any]) -> RedisConfig:
    """Retrieve producer configuration from settings."""
    try:
        LOGGER.debug("Constructing config from: %s", settings.get("plugin_config"))
        config_dict = settings["plugin_config"].get("redis_queue", {})
        LOGGER.debug("Retrieved: %s", config_dict)
        config_dict = process_config_dict(config_dict)
        config = RedisConfig(**config_dict)
    except KeyError:
        LOGGER.warning("Using default configuration")
        config = RedisConfig.default()

    LOGGER.debug("Returning config: %s", config.json(indent=2))
    LOGGER.debug("Returning config(aliases): %s", config.json(by_alias=True, indent=2))
    return config
