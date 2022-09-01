"""Redis Queue configuration."""

import logging
from typing import Any, Mapping, Optional
from pydantic import BaseModel, validator


LOGGER = logging.getLogger(__name__)

EVENT_TOPIC_MAP = {
    "^acapy::webhook::(.*)$": "acapy-webhook-$wallet_id",
    "^acapy::record::([^:]*)::([^:]*)$": "acapy-record-with-state-$wallet_id",
    "^acapy::record::([^:])?": "acapy-record-$wallet_id",
    "acapy::basicmessage::received": "acapy-basicmessage-received",
    "acapy::problem_report": "acapy-problem_report",
    "acapy::ping::received": "acapy-ping-received",
    "acapy::ping::response_received": "acapy-ping-response_received",
    "acapy::actionmenu::received": "acapy-actionmenu-received",
    "acapy::actionmenu::get-active-menu": "acapy-actionmenu-get-active-menu",
    "acapy::actionmenu::perform-menu-action": "acapy-actionmenu-perform-menu-action",
    "acapy::keylist::updated": "acapy-keylist-updated",
    "acapy::revocation-notification::received": "acapy-revocation-notification-received",
    "acapy::revocation-notification-v2::received": "acapy-revocation-notification-v2-received",
    "acapy::forward::received": "acapy-forward-received",
}

EVENT_WEBHOOK_TOPIC_MAP = {
    "acapy::basicmessage::received": "basicmessages",
    "acapy::problem_report": "problem_report",
    "acapy::ping::received": "ping",
    "acapy::ping::response_received": "ping",
    "acapy::actionmenu::received": "actionmenu",
    "acapy::actionmenu::get-active-menu": "get-active-menu",
    "acapy::actionmenu::perform-menu-action": "perform-menu-action",
    "acapy::keylist::updated": "keylist",
}


def _alias_generator(key: str) -> str:
    return key.replace("_", "-")


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


class ConnectionConfig(BaseModel):
    connection_url: str

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(connection_url="redis://default:test1234@172.28.0.103:6379")


class EventConfig(NoneDefaultModel):
    event_topic_maps: Mapping[str, str] = EVENT_TOPIC_MAP
    event_webhook_topic_maps: Mapping[str, str] = EVENT_WEBHOOK_TOPIC_MAP
    deliver_webhook: bool = True

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(
            event_topic_maps=EVENT_TOPIC_MAP,
            event_webhook_topic_maps=EVENT_WEBHOOK_TOPIC_MAP,
            deliver_webhook=True,
        )


class InboundConfig(NoneDefaultModel):
    acapy_inbound_topic: str = "acapy_inbound"
    acapy_direct_resp_topic: str = "acapy_inbound_direct_resp"

    class Config:
        alias_generator = _alias_generator
        allow_population_by_field_name = True

    @classmethod
    def default(cls):
        return cls(
            acapy_inbound_topic="acapy_inbound",
            acapy_direct_resp_topic="acapy_inbound_direct_resp",
        )


class OutboundConfig(NoneDefaultModel):
    acapy_outbound_topic: str = "acapy_outbound"
    mediator_mode: bool = False

    @classmethod
    def default(cls):
        return cls(
            acapy_outbound_topic="acapy_outbound",
            mediator_mode=False,
        )


class RedisConfig(BaseModel):
    event: Optional[EventConfig]
    inbound: Optional[InboundConfig]
    outbound: Optional[OutboundConfig]
    connection: ConnectionConfig

    @classmethod
    def default(cls):
        return cls(
            event=EventConfig.default(),
            inbound=InboundConfig.default(),
            outbound=OutboundConfig.default(),
            connection=ConnectionConfig.default(),
        )


def process_config_dict(config_dict: dict) -> dict:
    """Add connection to inbound, outbound, event and return updated config."""
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
