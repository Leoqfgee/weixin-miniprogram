from flask import Blueprint, current_app, g, request

from ..services.engagement import AiService
from ..utils.jwt import auth_required
from ..utils.response import success_response

ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/ai/product-copy")
@auth_required
def product_copy():
    data = AiService(current_app.db, current_app.config).product_copy(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)


@ai_bp.post("/ai/title")
@auth_required
def title():
    data = AiService(current_app.db, current_app.config).generate(g.current_user_id, request.get_json(silent=True) or {}, "title")
    return success_response(data)


@ai_bp.post("/ai/polish")
@auth_required
def polish():
    data = AiService(current_app.db, current_app.config).generate(g.current_user_id, request.get_json(silent=True) or {}, "polish")
    return success_response(data)


@ai_bp.post("/ai/description")
@auth_required
def description():
    data = AiService(current_app.db, current_app.config).generate(g.current_user_id, request.get_json(silent=True) or {}, "description")
    return success_response(data)
