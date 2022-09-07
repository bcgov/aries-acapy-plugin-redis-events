Aries Cloud Agent - Redis Events Plugin Demo
=================================================

This folder contains configs for multiple scenarios:

- A single agent with relay as http bridge networked with ngrok to be reachable from the outside world.
- A single agent setup with a mediator as http bridge networked with ngrok.

## Disclaimer: On the usage of ngrok

For each of the scenarios listed above, ngrok is used to simplify networking
between the host and containers. As a result of the toolbox generally running
directly on the host and the containers needing to communicate with each other
as well as the host, there is not a platform agnostic method of using the same
endpoint from all perspectives and reaching the intended agent. On Linux, this
is as simple as using the `host` network mode. On Mac and Windows, since docker
itself essentially runs in a VM, networking is not so flexible. From within the
container, `localhost` points to itself, `docker.host.internal` points to the
host, and other containers are reached by service name. From the host,
containers are only reachable through ports on `localhost`. In theory, one could
add aliases to each container on the host machine but this adds setup steps that
are not easily reversed when the containers are stopped and removed.

To circumvent these complexities, ngrok is used in these demos to provide an
endpoint that is consistently reachable from both the container cohort and the
host. This also comes with the side benefit of the demo agents being accessible
to other agents if, for instance, you would like to experiment with agents with
a peer.

Ngrok is not without limitations. Requests will be throttled after exceeding a
certain threshold and endpoints will expire after a set length of time, usually
on the range of a few hours. This means all connections formed will also expire
after a few hours. **These setups are for demonstration purposes only and should
not be used in production.**

In practice, Aries Cloud Agent - Python is deployed behind typical web
infrastructure to provide a consistent endpoint.

## Running the Demos

Requirements:
- Docker
- Docker Compose

For redis-ui GUI viewer, in `setup/p3x-redis-ui-settings/.p3xrs-conns.json` replace `"host": "{your_ipv4_address}"` with your local ipv4 address. This config is designed to work with redis cluster as setup inside `docker-compose.yml`, `docker-compose.relay.yml` and `redis.conf` files. Adjustments will be required in case these files are changed.

Both `Relay` and `Deliverer` service have the following service endpoints available:
- `GET` &emsp; `http://{STATUS_ENDPOINT_HOST}:{STATUS_ENDPOINT_PORT}/status/ready`
- `GET` &emsp; `http://{STATUS_ENDPOINT_HOST}:{STATUS_ENDPOINT_PORT}/status/live`

The configuration for the endpoint service can be provided as following for `relay` and `deliverer`. The API KEY should be provided in the header with `access_token` as key name.

```
environment:
    - STATUS_ENDPOINT_HOST=0.0.0.0
    - STATUS_ENDPOINT_PORT=7001
    - STATUS_ENDPOINT_API_KEY=test_api_key_1
```

#### Mediator as bridge

Run the following from the `demo` directory:

```sh
$ docker-compose up -d
```
This will start up the following:
- ACA-Py mediator [Edison Mediator] with `redis_queue.v1_0/outbound` setup such that inbound messages are pushed to `acapy_inbound_{recip_key}` queue
- Deliverer service to send outbound message from the `acapy_outbound` queue and deliver them to specified endpoints reliably.
- An agent [Adison Agency] with `redis_queue.v1_0/outbound` [`acapy_outbound` queue] and `redis_queue.v1_0/inbound`. This agent picks up message from the inbound queue being pushed in by the mediator.

Admin API will be availble at `http://0.0.0.0:3001` for test and demo purpose.
#### Relay as bridge

Run the following from the `demo` directory:

```sh
$ docker-compose -f ./docker-compose.relay.yml up -d
```
This will start up the following:
- Relay service to receive inbound message [`http` port `80`], extract `recip_key` and push such messages to `acapy_inbound_{recip_key}` queue. Supports both `http` and `ws`.
- Deliverer service to send outbound message from the `acapy_outbound` queue and deliver them to specified endpoints reliably.
- An agent [Adison Agency] with `redis_queue.v1_0/outbound` [`acapy_outbound` queue] and `redis_queue.v1_0/inbound`. This agent picks up message from the inbound queue being pushed in by the mediator.

Admin API will be availble at `http://0.0.0.0:3001` for test and demo purpose.
