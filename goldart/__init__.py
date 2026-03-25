import logging
import traceback
from flask import Flask, jsonify, session, redirect, url_for, request, render_template
from goldart.config import SECRET_KEY, ACCOUNT_BALANCE
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

    @app.context_processor
    def inject_sidebar_data():
        """Provide real balance + daily status to every template via sidebar."""
        if "user_id" not in session:
            return {}
        try:
            from goldart.database.queries import get_stats_summary
            stats = get_stats_summary(session["user_id"])
            balance = ACCOUNT_BALANCE + stats["total_pnl"]
            return {"sidebar_balance": balance, "sidebar_pnl": stats["total_pnl"]}
        except Exception:
            return {"sidebar_balance": ACCOUNT_BALANCE, "sidebar_pnl": 0}

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html",
            icon="◇",
            title="Page not found",
            message="The page you're looking for doesn't exist.",
        ), 404

    @app.errorhandler(500)
    def server_error(e):
        tb = traceback.format_exc()
        logging.error("500 error on %s: %s\n%s", request.url, e, tb)
        return render_template("error.html",
            icon="⚠",
            title="Something went wrong",
            message=f"{request.method} {request.path} failed — {e.__class__.__name__}: {e}",
            detail=tb if tb.strip() != "NoneType: None" else str(e),
        ), 500

    @app.get("/health")
    def health():
        return jsonify({"ok": _DB_OK, "db": "up" if _DB_OK else "down"})

    return app
