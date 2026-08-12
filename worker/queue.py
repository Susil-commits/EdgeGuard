"""Worker task queue — Redis/RQ setup and job enqueueing helpers."""

import redis
from rq import Queue

from api.config import settings

_redis_conn: redis.Redis | None = None
_queue: Queue | None = None


def get_redis() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis.from_url(settings.REDIS_URL)
    return _redis_conn


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue("edgeguard", connection=get_redis())
    return _queue


def enqueue_evaluation(node_id: str) -> None:
    """Enqueue a rule-evaluation job for a node after telemetry ingestion."""
    from worker.tasks.evaluate import run_evaluation  # avoid circular import

    get_queue().enqueue(run_evaluation, node_id, job_timeout=60)
