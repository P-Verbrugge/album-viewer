"""
Thin entry point: creates the Flask app via the application factory in
album_app/. Kept at the repo root so Docker/gunicorn can keep pointing at
"app:app" without any changes.
"""

from album_app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
