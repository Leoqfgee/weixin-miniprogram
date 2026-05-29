from app import create_app
from app.config import Config


app = create_app()


if __name__ == "__main__":
    # Windows 下 Flask debug reloader 偶发 WinError 10038；本地课程演示关闭自动重载更稳定。
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=app.config["DEBUG"], use_reloader=False)
