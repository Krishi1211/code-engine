import os
import time

from tasks import r, active_key

RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
MAX_CODE_BYTES = int(os.getenv("MAX_CODE_BYTES", "65536"))
ACTIVE_TTL = 300  # safety net so a crashed worker cannot pin a user's slots forever


def check_rate(user):
    """Fixed-window limit. Returns seconds to wait, or 0 if allowed."""
    window = int(time.time() // 60)
    key = f"rate:{user}:{window}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 60)
    if count > RATE_LIMIT:
        return 60 - int(time.time() % 60)
    return 0


def acquire_slot(user):
    key = active_key(user)
    active = r.incr(key)
    r.expire(key, ACTIVE_TTL)
    if active > MAX_CONCURRENT:
        r.decr(key)
        return False
    return True


def release_slot(user):
    if r.decr(active_key(user)) < 0:
        r.set(active_key(user), 0)
