"""Eagerly import task modules so Celery autodiscovery registers them."""

import importlib

importlib.import_module("app.workers.tasks.events_tasks")
importlib.import_module("app.workers.tasks.system_tasks")
