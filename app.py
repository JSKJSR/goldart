# app.py — thin entry point, only wires things together
from flask import Flask
from config import SECRET_KEY
from db.models import init_db
from routes.dashboard import dashboard_bp
from routes.analysis  import analysis_bp
from routes.trades    import trades_bp
from routes.export    import export_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    init_db()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp,  url_prefix="/analysis")
    app.register_blueprint(trades_bp,    url_prefix="/trades")
    app.register_blueprint(export_bp,    url_prefix="/export")

    return app

if __name__ == "__main__":
    create_app().run(debug=True, port=8080)
