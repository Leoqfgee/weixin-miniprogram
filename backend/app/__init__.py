from flask import Flask
from flask_cors import CORS

from .blueprints.admin import admin_bp
from .blueprints.ai import ai_bp
from .blueprints.auth import auth_bp
from .blueprints.cart import cart_bp
from .blueprints.categories import categories_bp
from .blueprints.deliveries import deliveries_bp
from .blueprints.health import health_bp
from .blueprints.messages import messages_bp
from .blueprints.orders import orders_bp
from .blueprints.payments import payments_bp
from .blueprints.products import products_bp
from .blueprints.refunds import refunds_bp
from .blueprints.reviews import reviews_bp
from .blueprints.users import users_bp
from .config import Config
from .extensions import mongo
from .utils.errors import register_error_handlers
from .utils.trace import register_trace_hooks


def create_app(config_class=Config):
    """Flask 应用工厂，后续所有业务 Blueprint 都从这里挂载。"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    mongo.init_app(app)
    register_trace_hooks(app)
    register_error_handlers(app)

    api_prefix = app.config["API_PREFIX"]
    app.register_blueprint(health_bp, url_prefix=api_prefix)
    app.register_blueprint(auth_bp, url_prefix=api_prefix)
    app.register_blueprint(users_bp, url_prefix=api_prefix)
    app.register_blueprint(categories_bp, url_prefix=api_prefix)
    app.register_blueprint(products_bp, url_prefix=api_prefix)
    app.register_blueprint(admin_bp, url_prefix=api_prefix)
    app.register_blueprint(cart_bp, url_prefix=api_prefix)
    app.register_blueprint(orders_bp, url_prefix=api_prefix)
    app.register_blueprint(payments_bp, url_prefix=api_prefix)
    app.register_blueprint(deliveries_bp, url_prefix=api_prefix)
    app.register_blueprint(messages_bp, url_prefix=api_prefix)
    app.register_blueprint(reviews_bp, url_prefix=api_prefix)
    app.register_blueprint(refunds_bp, url_prefix=api_prefix)
    app.register_blueprint(ai_bp, url_prefix=api_prefix)

    @app.teardown_appcontext
    def _close_mongo(exception=None):
        # Flask 开发服务器会频繁创建上下文，MongoClient 本身会连接池复用。
        return None

    return app
