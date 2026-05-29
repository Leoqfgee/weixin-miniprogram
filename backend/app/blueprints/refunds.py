from flask import Blueprint, current_app, g, request

from ..services.engagement import RefundService
from ..utils.jwt import auth_required
from ..utils.response import success_response

refunds_bp = Blueprint("refunds", __name__)


@refunds_bp.post("/refunds")
@auth_required
def create_refund():
    data = RefundService(current_app.db).create_refund(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@refunds_bp.get("/refunds")
@auth_required
def list_refunds():
    data = RefundService(current_app.db).list_refunds(g.current_user, request.args)
    return success_response(data)


@refunds_bp.get("/refunds/<refund_id>")
@auth_required
def get_refund(refund_id):
    data = RefundService(current_app.db).get_refund(refund_id, g.current_user)
    return success_response(data)


@refunds_bp.post("/refunds/<refund_id>/seller-handle")
@auth_required
def seller_handle(refund_id):
    data = RefundService(current_app.db).seller_handle(
        refund_id,
        g.current_user_id,
        request.get_json(silent=True) or {},
    )
    return success_response(data)
