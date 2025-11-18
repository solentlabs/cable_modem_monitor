# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dev tools
RUN pip install --upgrade pip \
    && pip install black ruff mypy pytest

# Set default Python path for tooling
ENV PYTHONPATH=/workspace
