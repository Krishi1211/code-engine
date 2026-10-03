# code-engine

A sandboxed multi-language code execution engine — think a mini Judge0.

## Features
- [x] Docker sandbox setup
- [x] REST API for code submission
- [x] Multi-language support (Python, JS, C++)
- [x] Async job queue with Redis / Celery
- [x] WebSocket real-time output streaming
- [x] Rate limiting + per-user resource caps
- [x] Frontend editor + auth

## Stack
Python, Docker, Redis, Celery, Next.js

## Prerequisites
Docker Desktop installed and running.

## Run locally
```bash
docker run hello-world
docker run --rm python:3.11-slim python -c "print('sandbox works')"
```

## Run the full stack
Redis must be running on `localhost:6379`.
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=change-me        # signs login tokens; random per start if unset
celery -A tasks worker --loglevel=info   # terminal 1
python app.py                            # terminal 2
```
Open http://localhost:5001 for the editor: register, pick a language, press Run,
and output streams in line by line.

## API
```
POST /register        body: {"username": "...", "password": "..."}  -> {"token"}
POST /login           body: {"username": "...", "password": "..."}  -> {"token"}
POST /submit          body: {"language": "python", "code": "..."}   -> {"job_id"}
GET  /result/<job_id>                                               -> status + result
GET  /languages
WS   /ws/<job_id>     send the token as the first message, then receive
                      {"event": "output", "stream": "stdout", "data": "..."} per line
                      and a final {"event": "done", "exit_code": 0}
```
`/submit` and `/result` need `Authorization: Bearer <token>`. Jobs are only
visible to the user who submitted them.

## Limits
| Limit | Default | Env var |
|---|---|---|
| Submissions per user per minute | 10 | `RATE_LIMIT_PER_MINUTE` |
| Concurrent jobs per user | 2 | `MAX_CONCURRENT_JOBS` |
| Code size | 64 KB | `MAX_CODE_BYTES` |

Each job runs in a container with 128 MB memory, half a CPU, 64 processes,
no network, a 60 second timeout and 1 MB of captured output.
