from flask import Blueprint, current_app, request

from ..services.users import AuthService
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
