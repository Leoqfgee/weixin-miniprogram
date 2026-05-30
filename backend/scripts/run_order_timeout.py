import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.tasks.order_timeout import run_order_timeout_tasks  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        summary = run_order_timeout_tasks(app.db, app.config)
        print(summary)


if __name__ == "__main__":
    main()
