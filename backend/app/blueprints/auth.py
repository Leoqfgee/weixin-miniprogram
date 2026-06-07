from flask import Blueprint, current_app, g, request

from ..services.users import AuthService
from ..utils.jwt import auth_required
from ..utils.errors import ValidationError
from ..utils.response import success_response

auth_bp = Blueprint("auth", __name__)


def _mask_appid(appid):
    if not appid:
        return ""
    if len(appid) <= 8:
        return f"{appid[:2]}***{appid[-2:]}"
    return f"{appid[:6]}***{appid[-4:]}"


@auth_bp.get("/auth/wechat-config")
def wechat_config():
    token = current_app.config.get("INIT_TOKEN")
    if not token or request.headers.get("X-Init-Token") != token:
        from ..utils.errors import UnauthorizedError

        raise UnauthorizedError("调试口令无效")
    appid = current_app.config.get("WECHAT_APPID", "")
    secret = current_app.config.get("WECHAT_SECRET", "")
    return success_response(
        {
            "wechat_auth_mode": current_app.config.get("WECHAT_AUTH_MODE", ""),
            "appid_masked": _mask_appid(appid),
            "appid_length": len(appid),
            "has_secret": bool(secret),
            "secret_length": len(secret),
        }
    )


@auth_bp.post("/auth/password-login")
def password_login():
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
    data = AuthService(current_app.db).password_login(phone, password)
    return success_response(data)


@auth_bp.post("/auth/dev-test-login")
def dev_test_login():
    payload = request.get_json(silent=True) or {}
    account = (payload.get("account") or "").strip()
    data = AuthService(current_app.db).dev_test_login(
        account,
        enabled=current_app.config.get("DEV_TEST_LOGIN_ENABLED", False),
    )
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
