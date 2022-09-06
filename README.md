# ACA-PY Redis Queue Plugin

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

## Documentation
#### Design
Covered in ./redis_queue/README.md

#### Demo
Covered in ./demo/README.md

#### Docker
Covered in ./docker.README.md

## Installation and Usage

First, install this plugin into your environment.

```sh
$ pip install git+https://github.com/bcgov/aries-acapy-plugin-redis-events.git
```

When starting up ACA-Py, load the plugin along with any other startup
parameters.

```sh
$ aca-py start --arg-file my_config.yml --plugin redis_queue.v1_0.events
```

## Plugin configuration
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
- `redis_queue.connection.connection_url`: This is required and is expected in `redis://{username}:{password}@{host}:{port}` format.
- `redis_queue.inbound.acapy_inbound_topic`: This is the topic prefix for the inbound message queues. Recipient key of the message are also included in the complete topic name. The final topic will be in the following format `acapy_inbound_{recip_key}`
- `redis_queue.inbound.acapy_direct_resp_topic`: Queue topic name for direct responses to inbound message.
- `redis_queue.outbound.acapy_outbound_topic`: Queue topic name for the outbound messages. Used by Deliverer service to deliver the payloads to specified endpoint.
- `redis_queue.outbound.mediator_mode`: Set to true, if using Redis as a http bridge when setting up a mediator agent. By default, it is set to false.
- `event.event_topic_maps`: Event topic map
- `event.event_webhook_topic_maps`: Event to webhook topic map
- `event.deliver_webhook`: When set to true, this will deliver webhooks to endpoints specified in `admin.webhook_urls`. By default, set to true.


## Plugin deployment
Once the plugin config is filled up. It is possible to deploy the plugin inside ACA-Py.
```shell
$ aca-py start \
    --plugin redis_queue \
    --plugin-config plugins-config.yaml \
    -it redis_queue.v1_0.inbound redis 0 -oq redis_queue.v1_0.outbound
    # ... the remainder of your startup arguments
```
