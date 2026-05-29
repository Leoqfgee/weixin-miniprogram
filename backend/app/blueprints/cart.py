from flask import Blueprint, current_app, g, request

from ..services.cart import CartService
from ..utils.jwt import auth_required
from ..utils.response import success_response

cart_bp = Blueprint("cart", __name__)


@cart_bp.post("/cart/items")
@auth_required
def add_cart_item():
    payload = request.get_json(silent=True) or {}
    data = CartService(current_app.db).add_item(g.current_user_id, payload)
    return success_response(data, http_status=201)


@cart_bp.get("/cart")
@auth_required
def get_cart():
    data = CartService(current_app.db).get_cart(g.current_user_id)
    return success_response(data)


@cart_bp.put("/cart/items/<product_id>")
@auth_required
def update_cart_item(product_id):
    payload = request.get_json(silent=True) or {}
    data = CartService(current_app.db).update_item(g.current_user_id, product_id, payload)
    return success_response(data)


@cart_bp.delete("/cart/items/<product_id>")
@auth_required
def delete_cart_item(product_id):
    data = CartService(current_app.db).delete_item(g.current_user_id, product_id)
    return success_response(data)
