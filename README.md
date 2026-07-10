# code-engine

A sandboxed multi-language code execution engine — think a mini Judge0.

## Features (in progress)
- [x] Docker sandbox setup
- [x] REST API for code submission
- [x] Multi-language support (Python, JS, C++)
- [ ] Async job queue with Redis / Celery
- [ ] WebSocket real-time output streaming
- [ ] Rate limiting + per-user resource caps
- [ ] Frontend editor + auth

## Stack
Python, Docker, Redis, Celery, Next.js

## Prerequisites
Docker Desktop installed and running.

## Run locally
```bash
docker run hello-world
docker run --rm python:3.11-slim python -c "print('sandbox works')"
```