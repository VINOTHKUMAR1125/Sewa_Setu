# -*- coding: utf-8 -*-
"""Entry point: `gunicorn app:app`. The application lives in the sewasetu package."""
from sewasetu import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
