from flask import Blueprint, current_app, g, request

from ..services.engagement import ReviewService
from ..utils.jwt import auth_required
from ..utils.response import success_response

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.post("/reviews")
@auth_required
def create_review():
    data = ReviewService(current_app.db).create_review(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)
