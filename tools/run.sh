#!/bin/bash

set -a
. .env
mkdir -p ${OUTPUT_DIR}
docker compose --env-file .env -f ./docker/docker-compose.yaml up --build