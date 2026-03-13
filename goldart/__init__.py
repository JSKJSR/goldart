import logging
from flask import Flask, jsonify, session, redirect, url_for, request
from goldart.config import SECRET_KEY
from goldart.database.models import init_db
from goldart.blueprints.dashboard import dashboard_bp
from goldart.blueprints.analysis  import analysis_bp
from goldart.blueprints.trades    import trades_bp
from goldart.blueprints.export    import export_bp
from goldart.blueprints.auth      import auth_bp

_DB_OK = False

# Endpoints that don't require authentication
_PUBLIC_ENDPOINTS = frozenset({"auth.login", "auth.login_post",
                               "auth.register", "auth.register_post",
                               "health", "static"})

def create_app():
    global _DB_OK
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')
    app.secret_key = SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    try:
        init_db()
        _DB_OK = True
    except Exception as exc:
        logging.exception("init_db() failed at startup — app will start without DB: %s", exc)
        _DB_OK = False

    app.register_blueprint(auth_bp,       url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp,   url_prefix="/analysis")
    app.register_blueprint(trades_bp,     url_prefix="/trades")
    app.register_blueprint(export_bp,     url_prefix="/export")

    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint and (endpoint in _PUBLIC_ENDPOINTS or endpoint.startswith("static")):
            return None
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return None

    @app.get("/health")
    def health():
        return jsonify({"ok": _DB_OK, "db": "up" if _DB_OK else "down"})

    return app
