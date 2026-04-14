"""Flask application for the local web UI."""

from __future__ import annotations

from flask import Flask, render_template

from core.config import load_settings


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    @app.get("/")
    def index() -> str:
        settings = load_settings()
        return render_template(
            "index.html",
            model=settings.get("model", ""),
            category_id=settings.get("category_id", ""),
        )

    return app


app = create_app()
