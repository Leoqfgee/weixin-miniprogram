from flask import Blueprint, current_app, g, request

from ..services.users import UserService
from ..utils.jwt import auth_required
from ..utils.response import success_response

users_bp = Blueprint("users", __name__)


@users_bp.get("/users/me")
@auth_required
def get_me():
    data = UserService(current_app.db).get_me(g.current_user_id)
    return success_response(data)


@users_bp.put("/users/me")
@auth_required
def update_me():
    data = UserService(current_app.db).update_me(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)


@users_bp.delete("/users/me")
@auth_required
def cancel_me():
    data = UserService(current_app.db).cancel_account(g.current_user_id)
    return success_response(data)


@users_bp.get("/users/<user_id>/profile")
def get_public_profile(user_id):
    data = UserService(current_app.db).get_public_profile(user_id)
    return success_response(data)
