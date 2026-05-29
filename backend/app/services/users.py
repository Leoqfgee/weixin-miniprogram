from werkzeug.security import check_password_hash

from ..repositories.users import UserRepository
from ..utils.errors import UnauthorizedError
from ..utils.jwt import create_token
from ..utils.serializers import serialize_doc


class AuthService:
    def __init__(self, db):
        self.users = UserRepository(db)

    def mock_login(self, phone, password):
        user = self.users.find_by_phone(phone)
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            raise UnauthorizedError("手机号或密码错误")
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")

        profile = self.users.find_profile(user["_id"])
        token = create_token(user["_id"], user.get("roles", []))
        return {"token": token, "user": build_user_summary(user, profile)}


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
