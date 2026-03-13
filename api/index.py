# api/index.py — Vercel serverless entry point
# Adds project root to path so all imports resolve correctly,
# then exposes the Flask app as `app` (required by @vercel/python).

import sys
import os

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goldart import create_app

app = create_app()
