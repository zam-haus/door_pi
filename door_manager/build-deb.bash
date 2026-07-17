#!/bin/bash
set -e

PROJECT_DIR="$(pwd)"
PROJECT_NAME=$(basename "$PROJECT_DIR")
PARENT_DIR="$(dirname "$PROJECT_DIR")"

podman run --rm -it \
  --name "deb-build-$PROJECT_NAME" \
  -v "$PARENT_DIR":/workspace:Z \
  -w /workspace/"$PROJECT_NAME" \
  debian:bookworm bash -e -c "
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y devscripts build-essential dh-python python3-all python3-setuptools python3-pip fakeroot python3-paho-mqtt pybuild-plugin-pyproject
    DEBIAN_FRONTEND=noninteractive dpkg -i python3-decorated-paho-mqtt_1.0.7_all.deb || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -f
    debuild -us -uc
  "
