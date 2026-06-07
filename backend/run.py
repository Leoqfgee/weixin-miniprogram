from app import create_app
from app.config import Config


app = create_app()


if __name__ == "__main__":
    # Keep the reloader disabled for stable Windows local demos.
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=app.config["DEBUG"],
        use_reloader=False,
    )
