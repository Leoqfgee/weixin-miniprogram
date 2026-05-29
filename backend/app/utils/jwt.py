from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app, g, request

from .errors import ForbiddenError, UnauthorizedError


def create_token(user_id, roles=None):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "roles": roles or [],
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=current_app.config["JWT_EXPIRES_SECONDS"])).timestamp()
        ),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("无效登录凭证") from exc


def get_current_user_from_request(required=False):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        if required:
            raise UnauthorizedError()
        return None
    if not auth_header.startswith("Bearer "):
        if required:
            raise UnauthorizedError()
        return None

    payload = decode_token(auth_header.split(" ", 1)[1].strip())
    user_id = payload.get("sub")
    if not user_id:
        if required:
            raise UnauthorizedError("登录凭证缺少用户信息")
        return None

    try:
        object_id = ObjectId(user_id)
    except InvalidId as exc:
        if required:
            raise UnauthorizedError("无效用户凭证") from exc
        return None

    user = current_app.db.users.find_one({"_id": object_id})
    if not user or user.get("status") in {"frozen", "disabled"}:
        if required:
            raise UnauthorizedError("账号不存在或已被禁用")
        return None
    return user


def auth_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user_from_request(required=True)
        g.current_user = user
        g.current_user_id = str(user["_id"])
        g.current_roles = user.get("roles", [])
        return view_func(*args, **kwargs)

    return wrapper


def roles_required(*required_roles):
    def decorator(view_func):
        @wraps(view_func)
        @auth_required
        def wrapper(*args, **kwargs):
            roles = set(getattr(g, "current_roles", []))
            if not roles.intersection(required_roles):
                raise ForbiddenError()
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
