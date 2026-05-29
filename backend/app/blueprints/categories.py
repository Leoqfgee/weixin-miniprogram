from flask import Blueprint, current_app

from ..services.categories import CategoryService
from ..utils.response import success_response

categories_bp = Blueprint("categories", __name__)


@categories_bp.get("/categories")
def list_categories():
    data = {"items": CategoryService(current_app.db).list_categories()}
    return success_response(data)
