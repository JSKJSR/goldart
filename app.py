# app.py — thin entry point, only wires things together
import logging
from flask import Flask, jsonify
from config import SECRET_KEY
from db.models import init_db
from routes.dashboard import dashboard_bp
from routes.analysis  import analysis_bp
from routes.trades    import trades_bp
from routes.export    import export_bp

_DB_OK = False   # set to True if init_db() succeeds at startup


def create_app():
    global _DB_OK
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    try:
        init_db()
        _DB_OK = True
    except Exception as exc:
        logging.exception("init_db() failed at startup — app will start without DB: %s", exc)
        _DB_OK = False

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp,  url_prefix="/analysis")
    app.register_blueprint(trades_bp,    url_prefix="/trades")
    app.register_blueprint(export_bp,    url_prefix="/export")

    @app.get("/health")
    def health():
        """Diagnostic endpoint — returns DB status without hitting routes."""
        return jsonify({"ok": _DB_OK, "db": "up" if _DB_OK else "down"})

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=8080)
