***REMOVED*** Use official Python 3.12 slim image
FROM python:3.12-slim

***REMOVED*** Set working directory inside container
WORKDIR /workspaces/cable_modem_monitor

***REMOVED*** Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    make \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

***REMOVED*** Upgrade pip and install basic dev tools only
RUN pip install --upgrade pip setuptools wheel

***REMOVED*** Set default Python path for tooling
ENV PYTHONPATH=/workspaces/cable_modem_monitor
