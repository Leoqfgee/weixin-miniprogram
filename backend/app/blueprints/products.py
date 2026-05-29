from flask import Blueprint, current_app, g, request

from ..services.products import ProductService
from ..utils.jwt import auth_required, get_current_user_from_request
from ..utils.response import success_response

products_bp = Blueprint("products", __name__)


@products_bp.get("/products")
def list_products():
    data = ProductService(current_app.db).list_products(request.args)
    return success_response(data)


@products_bp.get("/products/<product_id>")
def get_product(product_id):
    current_user = get_current_user_from_request(required=False)
    data = ProductService(current_app.db).get_product(product_id, current_user)
    return success_response(data)


@products_bp.post("/products")
@auth_required
def create_product():
    payload = request.get_json(silent=True) or {}
    data = ProductService(current_app.db).create_product(g.current_user_id, payload)
    return success_response(data, http_status=201)


@products_bp.put("/products/<product_id>")
@auth_required
def update_product(product_id):
    payload = request.get_json(silent=True) or {}
    data = ProductService(current_app.db).update_product(product_id, g.current_user_id, payload)
    return success_response(data)


@products_bp.post("/products/<product_id>/submit-review")
@auth_required
def submit_review(product_id):
    data = ProductService(current_app.db).submit_review(product_id, g.current_user_id)
    return success_response(data)


@products_bp.post("/products/<product_id>/off-shelf")
@auth_required
def off_shelf(product_id):
    payload = request.get_json(silent=True) or {}
    data = ProductService(current_app.db).off_shelf(
        product_id,
        g.current_user,
        payload=payload,
        trace_id=getattr(g, "trace_id", None),
    )
    return success_response(data)
