"""Celery application instance for Local Pulse workers."""

from celery import Celery

app = Celery("localpulse")
app.config_from_object("celery_config")
app.autodiscover_tasks(["tasks"])
