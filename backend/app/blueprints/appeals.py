from flask import Blueprint, current_app, g, request

from ..services.engagement import AppealService
from ..utils.jwt import auth_required
from ..utils.response import success_response

appeals_bp = Blueprint("appeals", __name__)


@appeals_bp.post("/appeals")
@auth_required
def create_appeal():
    data = AppealService(current_app.db).create_appeal(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@appeals_bp.get("/appeals/<appeal_id>")
@auth_required
def get_appeal(appeal_id):
    data = AppealService(current_app.db).get_appeal(appeal_id, g.current_user)
    return success_response(data)
