from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from celery import Celery, Task

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
celery_app = Celery(__name__)


def celery_init_app(app):
    """Wires Celery tasks so they run inside a Flask app context.

    Broker/backend is Redis (Memurai on this Windows dev box, a
    Redis-protocol-compatible server). See config.py's CELERY dict.
    """
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = FlaskTask
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app
