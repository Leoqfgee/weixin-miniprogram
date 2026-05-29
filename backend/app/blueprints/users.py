from flask import Blueprint, current_app, g

from ..services.users import UserService
from ..utils.jwt import auth_required
from ..utils.response import success_response

users_bp = Blueprint("users", __name__)


@users_bp.get("/users/me")
@auth_required
def get_me():
    data = UserService(current_app.db).get_me(g.current_user_id)
    return success_response(data)
