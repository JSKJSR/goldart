from __future__ import annotations

from flask import session


def get_current_user_id() -> int:
    return session["user_id"]
