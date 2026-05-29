from app import create_app


# 生产部署入口。云服务器上可用 gunicorn、uwsgi、waitress 等 WSGI Server 加载该对象。
app = create_app()
