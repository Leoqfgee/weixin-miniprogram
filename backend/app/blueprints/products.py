from flask import Blueprint, current_app, g, request

from ..services.products import FavoriteService, ProductService
from ..utils.jwt import auth_required, get_current_user_from_request
from ..utils.response import success_response

products_bp = Blueprint("products", __name__)


@products_bp.get("/products")
def list_products():
    current_user = get_current_user_from_request(required=False)
    data = ProductService(current_app.db).list_products(request.args, current_user)
    return success_response(data)


@products_bp.get("/products/mine")
@auth_required
def list_my_products():
    data = ProductService(current_app.db).list_my_products(g.current_user_id, request.args)
    return success_response(data)


@products_bp.get("/products/<product_id>")
def get_product(product_id):
    current_user = get_current_user_from_request(required=False)
    data = ProductService(current_app.db).get_product(product_id, current_user)
    return success_response(data)


@products_bp.get("/products/<product_id>/recommendations")
def list_product_recommendations(product_id):
    current_user = get_current_user_from_request(required=False)
    data = ProductService(current_app.db).list_recommendations(
        product_id,
        current_user,
        limit=request.args.get("limit", 6),
    )
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


@products_bp.post("/products/<product_id>/republish")
@auth_required
def republish_product(product_id):
    data = ProductService(current_app.db).republish_product(product_id, g.current_user_id)
    return success_response(data)


@products_bp.delete("/products/<product_id>")
@auth_required
def delete_product(product_id):
    data = ProductService(current_app.db).delete_product(product_id, g.current_user_id)
    return success_response(data)


@products_bp.get("/favorites")
@auth_required
def list_favorites():
    data = FavoriteService(current_app.db).list_favorites(
        g.current_user_id,
        favorite_type=(request.args.get("type") or "all").strip(),
    )
    return success_response(data)


@products_bp.post("/favorites")
@auth_required
def add_favorite():
    data = FavoriteService(current_app.db).add_favorite(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@products_bp.delete("/favorites/<product_id>")
@auth_required
def delete_favorite(product_id):
    data = FavoriteService(current_app.db).delete_favorite(g.current_user_id, product_id)
    return success_response(data)


@products_bp.post("/favorites/cleanup-invalid")
@auth_required
def cleanup_invalid_favorites():
    data = FavoriteService(current_app.db).cleanup_invalid(g.current_user_id)
    return success_response(data)
