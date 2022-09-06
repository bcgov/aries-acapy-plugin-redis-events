# Working with Docker Compose to run Integration tests

## Run integration test

To Run the integration tests:

```sh
docker-compose up --build
```

### Running with local changes.

To run the integration tests with changes in local directories, modify the
volume paths in `docker-compose.dev.yml` to reflect the paths to the plugin or
ACA-Py and run:

```sh
docker-compose -f int/docker-compose.yml -f int/docker-compose.dev.yml run tests \
	&& docker-compose -f int/docker-compose.yml stop
```

To see output from each of the services:

```sh
docker-compose up
```

To access individual service logs:

```
docker-compose logs <requester or resolver>
```

From the documentation:
```
Usage: logs [options] [SERVICE...]

Options:

--no-color Produce monochrome output.

-f, --follow Follow log output.

-t, --timestamps Show timestamps.

--tail="all" Number of lines to show from the end of the logs for each container.
```

You can start Docker compose in detached mode and attach yourself to the logs of
all container later. If you're done watching logs you can detach yourself from
the logs output without shutting down your services.

Use `docker-compose up -d` to start all services in detached mode (`-d`) (you
won't see any logs in detached mode)

Use `docker-compose logs -f -t` to attach yourself to the logs of all running
services, whereas `-f` means you follow the log output and the `-t` option gives you
timestamps (see Docker reference).

Use `Ctrl + z` or `Ctrl + c` to detach yourself from the log output without shutting
down your running containers.

If you're interested in logs of a single container you can use the docker
keyword instead:

```
docker logs -t -f <name-of-service>
```

To save the output to a file you add the following to your logs command:

```
docker-compose logs -f -t >> myDockerCompose.log
```
