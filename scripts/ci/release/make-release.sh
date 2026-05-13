#!/bin/bash

PROJECT_NAME="nanopore-compression-benchmarks"
CURRENT_DIR=$(pwd)

if [[ ! "$CURRENT_DIR" =~ $PROJECT_NAME$ ]] || [ ! -d ".git" ]; then
    echo "Error: This script must be run from the repository root ($PROJECT_NAME),"
    echo "but it was run from: $CURRENT_DIR"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker daemon is not running."
    exit 1
fi

FORCE_REFRESH=false
for arg in "$@"; do
    if [ "$arg" == "--force-refresh-builder" ]; then
        FORCE_REFRESH=true
        break
    fi
done

IMAGE_EXISTS=$(docker images -q pdz 2> /dev/null)

if [ -z "$IMAGE_EXISTS" ] || [ "$FORCE_REFRESH" = true ]; then
    echo "Building docker image 'pdz'..."
    docker build -t pdz:latest -f scripts/ci/release/linux-x86_64.Dockerfile .
else
    echo "Image 'pdz' already exists. Skipping build."
fi

mkdir -p $(pwd)/pre-compiled-bins/linux-x86_64
rm -rf $(pwd)/pre-compiled-bins/linux-x86_64/*

docker run -it \
  -v $(pwd)/pre-compiled-bins/linux-x86_64:/builder/artifacts \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  pdz
