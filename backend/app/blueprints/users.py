from flask import Blueprint, current_app, g, request

from ..services.users import UserService
from ..utils.jwt import auth_required, get_current_user_from_request
from ..utils.response import success_response

users_bp = Blueprint("users", __name__)


@users_bp.get("/users/me")
@auth_required
def get_me():
    data = UserService(current_app.db).get_me(g.current_user_id)
    return success_response(data)


@users_bp.get("/users/me/credit")
@auth_required
def get_my_credit():
    data = UserService(current_app.db).get_credit(g.current_user_id)
    return success_response(data)


@users_bp.get("/users/me/credit/records")
@auth_required
def list_my_credit_records():
    data = UserService(current_app.db).list_credit_records(g.current_user_id, request.args)
    return success_response(data)


@users_bp.get("/search")
def search_all():
    current_user = get_current_user_from_request(required=False)
    data = UserService(current_app.db).search_all(request.args, current_user=current_user)
    return success_response(data)


@users_bp.get("/search/meta")
def search_meta():
    current_user = get_current_user_from_request(required=False)
    data = UserService(current_app.db).search_meta(current_user)
    return success_response(data)


@users_bp.delete("/search/history")
@auth_required
def clear_search_history():
    data = UserService(current_app.db).clear_search_history(g.current_user_id)
    return success_response(data)


@users_bp.get("/users/search")
def search_users():
    data = UserService(current_app.db).search_users(request.args)
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
