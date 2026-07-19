from flask import Flask, session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import Config
from app.extensions import db, login_manager, migrate, mail, celery_init_app


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """WAL mode lets readers (e.g. the customer display polling every 2s)
    proceed without blocking a concurrent writer, and a longer busy_timeout
    gives SQLite a chance to retry instead of immediately raising "database
    is locked" under any contention. No-ops for non-SQLite connections.
    """
    if type(dbapi_connection).__module__.split(".")[0] != "sqlite3":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)
    celery_init_app(app)

    from app import tasks  # noqa: F401 - registers @celery_app.task functions

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.storefront.routes import storefront_bp
    from app.blueprints.pos.routes import pos_bp
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.api.routes import api_bp
    from app.blueprints.inventory.routes import inventory_bp
    from app.blueprints.account.routes import account_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(storefront_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(account_bp)

    @app.context_processor
    def inject_globals():
        from app.blueprints.account.routes import get_current_customer

        cart = session.get("cart", {})
        cart_count = sum(item["quantity"] for item in cart.values())
        return {
            "store_name": app.config["STORE_NAME"],
            "currency": app.config["CURRENCY"],
            "cart_count": cart_count,
            "current_customer": get_current_customer(),
        }

    @app.template_filter("ghs")
    def ghs_filter(value):
        return f"GH₵{float(value):,.2f}"

    return app
