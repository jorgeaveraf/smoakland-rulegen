# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps (for pandas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirement spec first (better cache)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default workdir has scripts/, templates/, data/, out/
ENV PYTHONUNBUFFERED=1
