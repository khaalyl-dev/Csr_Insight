"""
Flask application factory - main entry point of the backend.

This file creates the Flask app, loads configuration, connects to the database,
and registers all API blueprints (features). When you run 'python app.py', it
starts the server on port 5001.
"""
import logging
import os

from flask import Flask
from flask_cors import CORS

from config import Config
from core.db import db
from core.schema_patches import apply_schema_patches
from models import User  # noqa: F401 - needed for db.create_all
from socketio_instance import socketio

# Feature blueprints
from features.user_management import auth_bp, users_bp
from features.dashboard_analytics import dashboard_bp
from features.site_management import sites_bp, categories_bp, external_partners_bp
from features.csr_plan_management import csr_plans_bp, csr_import_bp
from features.planned_activity_management import planned_csr_bp
from features.realized_activity_management import realized_csr_bp
from features.validation_workflow_management import validations_bp
from features.change_request_management import change_requests_bp
from features.file_management import documents_bp
from features.audit_history_management import audit_bp
from features.notification_management import notifications_bp
from features.powerbi_integration import powerbi_bp
from features.chatbot_assistant import chatbot_bp
from features.health import health_bp
from features.task_management import tasks_bp


def create_app(config_class=Config) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class (from config.py) containing DB URL, SECRET_KEY, etc.

    Returns:
        The configured Flask app ready to serve API requests.
    """
    # Create the Flask app and load settings (database, secret key, etc.)
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Connect SQLAlchemy to our app so we can use db.session, db.Model, etc.
    db.init_app(app)

    # Create all database tables if they don't exist yet
    with app.app_context():
        db.create_all()
        apply_schema_patches(db)

    # Allow the Angular frontend (running on port 4200) to call our API from a different origin
    extra_origins_raw = (os.environ.get("FRONTEND_ORIGINS") or "").strip()
    extra_origins = [o.strip() for o in extra_origins_raw.split(",") if o.strip()]
    allowed_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        *extra_origins,
    ]

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "Accept"],
                "expose_headers": ["Content-Type", "Authorization"],
            }
        },
    )

    # Register blueprints - each blueprint adds API routes (e.g. /api/auth/login, /api/users, etc.)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sites_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(external_partners_bp)
    app.register_blueprint(csr_plans_bp)
    app.register_blueprint(csr_import_bp)  # /api/csr-plans/import-excel
    app.register_blueprint(planned_csr_bp)
    app.register_blueprint(realized_csr_bp)
    app.register_blueprint(validations_bp)
    app.register_blueprint(change_requests_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(powerbi_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(tasks_bp)

    socketio.init_app(app)
    # Register Socket.IO handlers (JWT on connect, notification rooms)
    import features.notification_management.socketio_events  # noqa: F401, PLC0415

    return app


app = create_app()


class SuppressServeLogFilter(logging.Filter):
    """
    Filter to hide logs for document-serve requests (e.g. profile photo loads).

    This reduces terminal noise when the frontend loads many small images.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to hide this log, True to show it."""
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(getattr(record, "msg", ""))
        if "/api/documents/serve/" in msg:
            return False
        return True


if __name__ == "__main__":
    # Attach filter to the logger so it applies to all handlers (including any added by werkzeug later)
    logging.getLogger("werkzeug").addFilter(SuppressServeLogFilter())
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=True,
        allow_unsafe_werkzeug=True,
    )
