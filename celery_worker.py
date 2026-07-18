"""Celery worker/beat entry point.

Run the worker (Windows needs --pool=solo; prefork isn't supported there):
    celery -A celery_worker.celery_app worker --loglevel=info --pool=solo

Run the beat scheduler (daily low-stock check, see config.py CELERY.beat_schedule):
    celery -A celery_worker.celery_app beat --loglevel=info
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app

flask_app = create_app()
flask_app.app_context().push()

celery_app = flask_app.extensions["celery"]
