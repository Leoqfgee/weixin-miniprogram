from flask import Blueprint, current_app, g, request

from ..services.users import AuthService
from ..utils.jwt import auth_required
from ..utils.errors import ValidationError
from ..utils.response import success_response

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/auth/mock-login")
def mock_login():
    payload = request.get_json(silent=True) or {}
    phone = (payload.get("phone") or "").strip()
    password = payload.get("password") or ""
    if not phone or not password:
        raise ValidationError(
            "参数校验失败",
            [
                {"field": "phone", "message": "手机号不能为空"},
                {"field": "password", "message": "密码不能为空"},
            ],
        )
    data = AuthService(current_app.db).mock_login(phone, password)
    return success_response(data)


@auth_bp.post("/auth/wechat-login")
def wechat_login():
    data = AuthService(current_app.db).wechat_login(request.get_json(silent=True) or {})
    return success_response(data)


@auth_bp.post("/auth/register")
def register():
    data = AuthService(current_app.db).register(request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@auth_bp.post("/auth/bind-phone")
@auth_required
def bind_phone():
    data = AuthService(current_app.db).bind_phone(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)


@auth_bp.post("/auth/change-password")
@auth_required
def change_password():
    data = AuthService(current_app.db).change_password(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data)


@auth_bp.post("/auth/logout")
@auth_required
def logout():
    return success_response(AuthService(current_app.db).logout())
