# routes/mentor.py — AI mentor trade analysis
from flask import Blueprint, render_template, jsonify, request
from goldart.blueprints.decorators import get_current_user_id
from goldart.services.mentor import get_mentor_analysis

mentor_bp = Blueprint("mentor", __name__)


@mentor_bp.get("/")
def index():
    return render_template("mentor.html")


@mentor_bp.post("/api/analyze")
def analyze():
    user_id = get_current_user_id()
    force = request.args.get("force", "0") == "1"
    result = get_mentor_analysis(user_id, force=force)
    return jsonify(result)
