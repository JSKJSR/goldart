from __future__ import annotations

import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from goldart.database.queries import create_user, get_user_by_username, get_user_by_email

auth_bp = Blueprint("auth", __name__)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


@auth_bp.get("/login")
def login():
    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = get_user_by_username(username)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid username or password.", "error")
        return render_template("login.html"), 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("dashboard.index"))


@auth_bp.get("/register")
def register():
    return render_template("register.html")


@auth_bp.post("/register")
def register_post():
    username = (request.form.get("username") or "").strip()
    email    = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm  = request.form.get("confirm") or ""

    # Validation
    if not _USERNAME_RE.match(username):
        flash("Username must be 3-50 characters (letters, numbers, underscore).", "error")
        return render_template("register.html"), 400

    if "@" not in email or "." not in email:
        flash("Please enter a valid email address.", "error")
        return render_template("register.html"), 400

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("register.html"), 400

    if password != confirm:
        flash("Passwords do not match.", "error")
        return render_template("register.html"), 400

    if get_user_by_username(username):
        flash("Username already taken.", "error")
        return render_template("register.html"), 400

    if get_user_by_email(email):
        flash("Email already registered.", "error")
        return render_template("register.html"), 400

    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    user_id = create_user(username, email, password_hash)

    session.clear()
    session["user_id"] = user_id
    session["username"] = username
    return redirect(url_for("dashboard.index"))


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
