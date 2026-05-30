from flask import Blueprint, current_app, g, request

from ..services.orders import DeliveryService
from ..utils.jwt import auth_required
from ..utils.response import success_response

deliveries_bp = Blueprint("deliveries", __name__)


@deliveries_bp.post("/deliveries/<order_id>/confirm")
@auth_required
def confirm_receipt(order_id):
    data = DeliveryService(current_app.db).buyer_confirm(order_id, g.current_user_id)
    return success_response(data)


@deliveries_bp.post("/deliveries/<order_id>/seller-deliver")
@auth_required
def seller_deliver(order_id):
    data = DeliveryService(current_app.db).seller_deliver(order_id, g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)


@deliveries_bp.get("/deliveries/<order_id>")
@auth_required
def get_delivery(order_id):
    data = DeliveryService(current_app.db).get_delivery(order_id, g.current_user_id)
    return success_response(data)


@deliveries_bp.post("/deliveries/<order_id>/buyer-confirm")
@auth_required
def buyer_confirm(order_id):
    data = DeliveryService(current_app.db).buyer_confirm(order_id, g.current_user_id)
    return success_response(data)


@deliveries_bp.post("/deliveries/<order_id>/buyer-reject")
@auth_required
def buyer_reject(order_id):
    data = DeliveryService(current_app.db).buyer_reject(order_id, g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)
