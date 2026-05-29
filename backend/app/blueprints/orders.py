from flask import Blueprint, current_app, g, request

from ..services.orders import OrderService
from ..utils.jwt import auth_required
from ..utils.response import success_response

orders_bp = Blueprint("orders", __name__)


@orders_bp.post("/orders")
@auth_required
def create_order():
    payload = request.get_json(silent=True) or {}
    idempotency_key = request.headers.get("X-Idempotency-Key") or payload.get("idempotency_key")
    data = OrderService(current_app.db).create_order(g.current_user_id, payload, idempotency_key)
    return success_response(data, http_status=201)


@orders_bp.get("/orders")
@auth_required
def list_orders():
    data = OrderService(current_app.db).list_orders(g.current_user_id, request.args)
    return success_response(data)


@orders_bp.get("/orders/<order_id>")
@auth_required
def get_order(order_id):
    data = OrderService(current_app.db).get_order(order_id, g.current_user_id)
    return success_response(data)


@orders_bp.post("/orders/<order_id>/cancel")
@auth_required
def cancel_order(order_id):
    data = OrderService(current_app.db).cancel_order(order_id, g.current_user_id)
    return success_response(data)
