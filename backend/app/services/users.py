from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from ..adapters.wechat import WechatAuthAdapter
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from ..utils.jwt import create_token
from ..utils.serializers import serialize_doc


def utc_now():
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db):
        self.users = UserRepository(db)
        self.wechat = WechatAuthAdapter()

    def mock_login(self, phone, password):
        user = self.users.find_by_phone(phone)
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            raise UnauthorizedError("手机号或密码错误")
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")

        profile = self.users.find_profile(user["_id"])
        token = create_token(user["_id"], user.get("roles", []))
        return {"token": token, "user": build_user_summary(user, profile)}

    def wechat_login(self, payload):
        session = self.wechat.code_to_session(payload.get("code"), payload.get("mock_openid"))
        openid = session.get("openid")
        if not openid:
            raise UnauthorizedError("微信登录失败，未获取 openid")
        user = self.users.find_by_openid(openid)
        if not user:
            nickname = (payload.get("nickname") or "微信用户").strip()
            avatar_url = (payload.get("avatar_url") or "").strip()
            user = self.users.create_user(
                {
                    "openid": openid,
                    "phone": "",
                    "password_hash": "",
                    "roles": ["buyer"],
                    "status": "active",
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                },
                {
                    "nickname": nickname,
                    "avatar_url": avatar_url,
                    "campus": "",
                    "student_no": "",
                    "verified_status": "unverified",
                    "credit_score": 100,
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                },
            )
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")
        profile = self.users.find_profile(user["_id"])
        token = create_token(user["_id"], user.get("roles", []))
        return {
            "token": token,
            "user": build_user_summary(user, profile),
            "need_bind_phone": not bool(user.get("phone")),
        }

    def register(self, payload):
        phone = _required_str(payload, "phone", "手机号不能为空")
        password = _required_str(payload, "password", "密码不能为空")
        if len(password) < 6:
            raise ValidationError("参数校验失败", [{"field": "password", "message": "密码至少 6 位"}])
        if self.users.find_by_phone(phone):
            raise ConflictError("手机号已注册")
        nickname = (payload.get("nickname") or "校园用户").strip()
        user = self.users.create_user(
            {
                "openid": payload.get("openid") or None,
                "phone": phone,
                "password_hash": generate_password_hash(password),
                "roles": ["buyer"],
                "status": "active",
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
            {
                "nickname": nickname,
                "avatar_url": "",
                "campus": (payload.get("campus") or "").strip(),
                "student_no": "",
                "verified_status": "unverified",
                "credit_score": 100,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        )
        profile = self.users.find_profile(user["_id"])
        token = create_token(user["_id"], user.get("roles", []))
        return {"token": token, "user": build_user_summary(user, profile)}

    def bind_phone(self, user_id, payload):
        phone = _required_str(payload, "phone", "手机号不能为空")
        password = payload.get("password") or ""
        existing = self.users.find_by_phone(phone)
        if existing and str(existing["_id"]) != str(user_id):
            raise ConflictError("手机号已被其他账号绑定")
        fields = {"phone": phone, "updated_at": utc_now()}
        if password:
            if len(password) < 6:
                raise ValidationError("参数校验失败", [{"field": "password", "message": "密码至少 6 位"}])
            fields["password_hash"] = generate_password_hash(password)
        user = self.users.update_user(user_id, fields)
        profile = self.users.find_profile(user["_id"])
        return build_user_summary(user, profile)

    def change_password(self, user_id, payload):
        old_password = payload.get("old_password") or ""
        new_password = payload.get("new_password") or ""
        if len(new_password) < 6:
            raise ValidationError("参数校验失败", [{"field": "new_password", "message": "新密码至少 6 位"}])
        user = self.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        if user.get("password_hash") and not check_password_hash(user.get("password_hash", ""), old_password):
            raise UnauthorizedError("原密码错误")
        user = self.users.update_user(user_id, {"password_hash": generate_password_hash(new_password), "updated_at": utc_now()})
        profile = self.users.find_profile(user["_id"])
        return build_user_summary(user, profile)

    def logout(self):
        return {"logged_out": True}


class UserService:
    def __init__(self, db):
        self.users = UserRepository(db)

    def get_me(self, user_id):
        user = self.users.find_by_id(user_id)
        profile = self.users.find_profile(user_id)
        return build_user_summary(user, profile)


def build_user_summary(user, profile=None):
    profile = profile or {}
    return {
        "id": str(user["_id"]),
        "phone": user.get("phone"),
        "roles": user.get("roles", []),
        "status": user.get("status"),
        "profile": serialize_doc(profile) or {},
    }


def _required_str(payload, field, message):
    value = (payload.get(field) or "").strip()
    if not value:
        raise ValidationError("参数校验失败", [{"field": field, "message": message}])
    return value
