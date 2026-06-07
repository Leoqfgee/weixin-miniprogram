from app import create_app


# Production WSGI entry point for gunicorn or other WSGI servers.
app = create_app()
