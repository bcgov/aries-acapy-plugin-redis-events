# ACA-PY Redis Queue Plugin - Has Moved! [![Lifecycle:Moved](https://img.shields.io/badge/Lifecycle-Moved-d45500)](https://github.com/hyperledger/aries-acapy-plugins/tree/main/redis_events)
[![Code Quality Check](https://github.com/bcgov/aries-acapy-plugin-redis-events/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/bcgov/aries-acapy-plugin-redis-events/actions/workflows/code-quality-check.yml)
[![Tests](https://github.com/bcgov/aries-acapy-plugin-redis-events/actions/workflows/tests.yml/badge.svg)](https://github.com/bcgov/aries-acapy-plugin-redis-events/actions/workflows/tests.yml)

## :warning: Move Notice :warning:
The ACA-PY Redis Queue Plugin has been donated to the Hyperledger Foundation Aries project and has been moved to its new home in the [hyperledger/aries-acapy-plugins](https://github.com/hyperledger/aries-acapy-plugins) repository.  You'll find it in the `redis_events` folder.

We're proud for the code to join the many other code contributions made by the Province of British Columbia to the Hyperledger Foundation.

This repository has been archived and will no longer be maintained.

## About the ACA-PY Redis Queue Plugin

This plugin provides mechansim to persists both inbound and outbound messages, deliver messages and webhooks, and dispatch events.

For receiving inbound messages, you have an option to either setup a mediator or a relay [supports [direct response](https://github.com/hyperledger/aries-rfcs/tree/main/features/0092-transport-return-route#aries-rfc-0092-transports-return-route)].

For the mediator scenario:

```mermaid
  flowchart LR;
      InboundMsg([Inbound Msg])-->Mediator;
      Mediator-->InboundQueue[(Inbound Queue)];
      InboundQueue-->YourAgent{{Your Agent}};
```

For the relay scenario:

```mermaid
  flowchart LR;
      InboundMsg([Inbound Msg])-->Relay;
      Relay-->InboundQueue[(Inbound Queue)];
      InboundQueue-->YourAgent{{Your Agent}};
```

The `demo` directory contains a working example/template for both:

- `docker-compose.yml` for `mediation`, and
- `docker-compose.relay.yml` for `relay`

The `deliverer` service dispatches the outbound messages and webhooks. For the `events`, the payload is pushed to the relevant Redis LIST [for the topic name, refer to [event.event_topic_maps](#plugin-configuration)] and further action is delegated to the controllers.

For the outbound scenario:

```mermaid
  flowchart LR;
      YourAgent{{Your Agent}}-->OutboundQueue[(Outbound Queue)];
      OutboundQueue-->Deliverer;
      Deliverer-->OutboundMsg([Outbound Msg]);
```

## Code Structure

The directory structure within this repository is as follows:

```
│
│
└───redis_deliverer
│   deliver.py
└───redis_queue
│   └───events
│   inbound
│   outbound
│   config
│   utils
└───redis_relay
│   └───relay
|   |   relay
└───status_endpoint
|   status_endpoint
└───int
└───demo
└───docker
|
```

The code for the Deliverer and Relay processes are in the `redis_deliverer` and `redis_relay` directories, respectively.  The `status_endpoint` directory contains code for health endpoints that is used by both of these processes.

The `docker` directory contains a dockerfile (and instructions) for running aca-py with the redis plugin.

The `demo` diretory contains example docker-compose files for running aca-py with redis using either of the Relay or Mediator scenarios.

## Documentation

#### Design

Covered in ./redis_queue/README.md

#### Demo

Covered in ./demo/README.md

#### Docker

Covered in ./docker/README.md

## Installation and Usage

First, install this plugin into your environment:

> **Note** Deployments of the main branch of this repository must be used with ACA-Py artifacts created **after** [ACA-Py PR #2170](https://github.com/hyperledger/aries-cloudagent-python/pull/2170)). If you are using an earlier ACA-Py release (e.g., version 0.8.2 and earlier), you **MUST** use the v0.0.1 tag of this repository.

```sh
$ pip install git+https://github.com/bcgov/aries-acapy-plugin-redis-events.git@v0.1.0
```

When starting up ACA-Py, load the plugin along with any other startup parameters:

```sh
$ aca-py start --arg-file my_config.yml --plugin redis_queue.v1_0.events
```

## Plugin configuration

The redis plugin is configured using an external yaml file.  An example yaml configuration is:

```yaml
redis_queue:
  connection:
    connection_url: "redis://default:test1234@172.28.0.103:6379"

  ### For Inbound ###
  inbound:
    acapy_inbound_topic: "acapy_inbound"
    acapy_direct_resp_topic: "acapy_inbound_direct_resp"

  ### For Outbound ###
  outbound:
    acapy_outbound_topic: "acapy_outbound"
    mediator_mode: false

  ### For Event ###
  event:
    event_topic_maps:
      ^acapy::webhook::(.*)$: acapy-webhook-$wallet_id
      ^acapy::record::([^:]*)::([^:]*)$: acapy-record-with-state-$wallet_id
      ^acapy::record::([^:])?: acapy-record-$wallet_id
      acapy::basicmessage::received: acapy-basicmessage-received
      acapy::problem_report: acapy-problem_report
      acapy::ping::received: acapy-ping-received
      acapy::ping::response_received: acapy-ping-response_received
      acapy::actionmenu::received: acapy-actionmenu-received
      acapy::actionmenu::get-active-menu: acapy-actionmenu-get-active-menu
      acapy::actionmenu::perform-menu-action: acapy-actionmenu-perform-menu-action
      acapy::keylist::updated: acapy-keylist-updated
      acapy::revocation-notification::received: acapy-revocation-notification-received
      acapy::revocation-notification-v2::received: acapy-revocation-notification-v2-received
      acapy::forward::received: acapy-forward-received
    event_webhook_topic_maps:
      acapy::basicmessage::received: basicmessages
      acapy::problem_report: problem_report
      acapy::ping::received: ping
      acapy::ping::response_received: ping
      acapy::actionmenu::received: actionmenu
      acapy::actionmenu::get-active-menu: get-active-menu
      acapy::actionmenu::perform-menu-action: perform-menu-action
      acapy::keylist::updated: keylist
    deliver_webhook: true
```

The configuration parameters in the above example are:

Connection:

- `redis_queue.connection.connection_url`: This is required and is expected in `redis://{username}:{password}@{host}:{port}` format.

Inbound:

- `redis_queue.inbound.acapy_inbound_topic`: This is the topic prefix for the inbound message queues. Recipient key of the message are also included in the complete topic name. The final topic will be in the following format `acapy_inbound_{recip_key}`
- `redis_queue.inbound.acapy_direct_resp_topic`: Queue topic name for direct responses to inbound message.

Outbound:

- `redis_queue.outbound.acapy_outbound_topic`: Queue topic name for the outbound messages. Used by Deliverer service to deliver the payloads to specified endpoint.
- `redis_queue.outbound.mediator_mode`: Set to true, if using Redis as a http bridge when setting up a mediator agent. By default, it is set to false.

Events:

- `event.event_topic_maps`: Event topic map
- `event.event_webhook_topic_maps`: Event to webhook topic map
- `event.deliver_webhook`: When set to true, this will deliver webhooks to endpoints specified in `admin.webhook_urls`. By default, set to true.


## Plugin deployment

Once the plugin config is defined, it is possible to deploy the plugin inside ACA-Py.

```shell
$ aca-py start \
    --plugin redis_queue.v1_0.events \
    --plugin-config plugins-config.yaml \
    -it redis_queue.v1_0.inbound redis 0 -ot redis_queue.v1_0.outbound
    # ... the remainder of your startup arguments
```

## Status Endpoints

`Relay` and `Deliverer` service have the following service endpoints available:

- `GET` &emsp; `http://{STATUS_ENDPOINT_HOST}:{STATUS_ENDPOINT_PORT}/status/ready`
- `GET` &emsp; `http://{STATUS_ENDPOINT_HOST}:{STATUS_ENDPOINT_PORT}/status/live`

The configuration for the endpoint service can be provided as following for `relay` and `deliverer`. The API KEY should be provided in the header with `access_token` as key name.

```
environment:
    - STATUS_ENDPOINT_HOST=0.0.0.0
    - STATUS_ENDPOINT_PORT=7001
    - STATUS_ENDPOINT_API_KEY=test_api_key_1
```
