# app/__init__.py
from .tasks import app as celery_app

__all__ = ('celery_app',)
