#!/bin/bash

set -a
mkdir -p workdir output_dir
docker compose -f ./docker/docker-compose.yaml up --build