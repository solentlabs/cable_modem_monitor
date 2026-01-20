# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /workspaces/cable_modem_monitor

# Install system dependencies
# procps provides ps/pkill (required for docker-in-docker)
# iptables required for docker networking
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    make \
    wget \
    unzip \
    procps \
    iptables \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install basic dev tools only
RUN pip install --upgrade pip setuptools wheel

# Set default Python path for tooling
ENV PYTHONPATH=/workspaces/cable_modem_monitor
