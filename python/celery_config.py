"""Celery configuration -- broker, backend, serialization, and task behavior."""

import os

from dotenv import load_dotenv

load_dotenv()

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# Re-deliver tasks if a worker crashes mid-execution
task_acks_late = True
worker_prefetch_multiplier = 1
task_reject_on_worker_lost = True

# Limit result storage
result_expires = 86400  # 24 hours
