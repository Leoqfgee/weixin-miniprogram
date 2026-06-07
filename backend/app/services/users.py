from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from ..adapters.wechat import WechatAuthAdapter
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from ..utils.jwt import create_token
from ..utils.serializers import serialize_doc, to_object_id


def utc_now():
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db):
        self.users = UserRepository(db)
        self.wechat = WechatAuthAdapter()

    def password_login(self, phone, password):
        user = self.users.find_by_phone(phone)
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            raise UnauthorizedError("手机号或密码错误")
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")

        profile = self.users.find_profile(user["_id"])
        token = create_token(user["_id"], user.get("roles", []))
        return {"token": token, "user": build_user_summary(user, profile)}

    def wechat_login(self, payload):
        session = self.wechat.code_to_session(payload.get("code"))
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
                    "phone": None,
                    "password_hash": "",
                    "roles": ["buyer", "seller"],
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
                "roles": ["buyer", "seller"],
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
        self.db = db
        self.users = UserRepository(db)
        self.products = ProductRepository(db)

    def get_me(self, user_id):
        user = self.users.find_by_id(user_id)
        profile = self.users.find_profile(user_id)
        return build_user_summary(user, profile)

    def update_me(self, user_id, payload):
        allowed = {"avatar", "avatar_url", "nickname", "campus", "bio"}
        unknown = set(payload.keys()) - allowed
        if unknown:
            raise ValidationError("参数校验失败", [{"field": ",".join(sorted(unknown)), "message": "包含不允许的字段"}])
        fields = {}
        if "avatar" in payload:
            fields["avatar"] = (payload.get("avatar") or "").strip()
            fields["avatar_url"] = fields["avatar"]
        if "avatar_url" in payload:
            fields["avatar_url"] = (payload.get("avatar_url") or "").strip()
            fields["avatar"] = fields["avatar_url"]
        if "nickname" in payload:
            nickname = (payload.get("nickname") or "").strip()
            if len(nickname) < 1 or len(nickname) > 30:
                raise ValidationError("参数校验失败", [{"field": "nickname", "message": "昵称需为 1-30 字"}])
            fields["nickname"] = nickname
        if "campus" in payload:
            fields["campus"] = (payload.get("campus") or "").strip()
        if "bio" in payload:
            bio = (payload.get("bio") or "").strip()
            if len(bio) > 120:
                raise ValidationError("参数校验失败", [{"field": "bio", "message": "简介不能超过 120 字"}])
            fields["bio"] = bio
        fields["updated_at"] = utc_now()
        profile = self.users.update_profile(user_id, fields)
        user = self.users.find_by_id(user_id)
        return build_user_summary(user, profile)

    def get_public_profile(self, user_id):
        user = self.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        profile = self.users.find_profile(user_id) or {}
        object_id = user["_id"]
        on_sale_products = list(self.db.products.find({"seller_id": object_id, "status": "on_sale", "deleted_at": {"$exists": False}}).sort("created_at", -1).limit(20))
        public_profile = {
            "id": str(object_id),
            "nickname": profile.get("nickname", "校园用户"),
            "avatar": profile.get("avatar") or profile.get("avatar_url", ""),
            "avatar_url": profile.get("avatar_url") or profile.get("avatar", ""),
            "campus": profile.get("campus", ""),
            "bio": profile.get("bio", ""),
            "credit_score": profile.get("credit_score", 100),
            "campus_verified": profile.get("verified_status") == "approved",
            "deal_count": self.db.orders.count_documents({"seller_id": object_id, "status": "completed"}),
            "publish_count": self.db.products.count_documents({"seller_id": object_id, "deleted_at": {"$exists": False}}),
            "sold_count": self.db.products.count_documents({"seller_id": object_id, "status": "sold"}),
        }
        review_count = self.db.reviews.count_documents({"reviewee_id": object_id})
        good_count = self.db.reviews.count_documents({"reviewee_id": object_id, "rating": {"$gte": 4}})
        public_profile["review_count"] = review_count
        public_profile["good_rate"] = round(good_count * 100 / review_count, 1) if review_count else 100.0
        return {
            "user": public_profile,
            "on_sale_products": [_public_product(item, profile) for item in on_sale_products],
            "reviews": _public_reviews(self.db, object_id),
        }


class AddressService:
    def __init__(self, db):
        self.db = db

    def list_addresses(self, user_id):
        items = list(
            self.db.addresses.find({"user_id": to_object_id(user_id, "user_id")})
            .sort([("is_default", -1), ("created_at", -1)])
        )
        return {"items": [serialize_doc(item) for item in items]}

    def create_address(self, user_id, payload):
        user_object_id = to_object_id(user_id, "user_id")
        fields = self._validate(payload)
        is_default = bool(payload.get("is_default")) or self.db.addresses.count_documents({"user_id": user_object_id}) == 0
        if is_default:
            self.db.addresses.update_many({"user_id": user_object_id}, {"$set": {"is_default": False, "updated_at": utc_now()}})
        doc = {
            "user_id": user_object_id,
            **fields,
            "is_default": is_default,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.addresses.insert_one(doc)
        return serialize_doc(self.db.addresses.find_one({"_id": result.inserted_id}))

    def update_address(self, user_id, address_id, payload):
        address = self._get_owned(user_id, address_id)
        fields = self._validate(payload)
        if payload.get("is_default"):
            self.db.addresses.update_many({"user_id": address["user_id"]}, {"$set": {"is_default": False, "updated_at": utc_now()}})
            fields["is_default"] = True
        fields["updated_at"] = utc_now()
        self.db.addresses.update_one({"_id": address["_id"]}, {"$set": fields})
        return serialize_doc(self.db.addresses.find_one({"_id": address["_id"]}))

    def delete_address(self, user_id, address_id):
        address = self._get_owned(user_id, address_id)
        self.db.addresses.delete_one({"_id": address["_id"]})
        if address.get("is_default"):
            replacement = self.db.addresses.find_one({"user_id": address["user_id"]}, sort=[("created_at", -1)])
            if replacement:
                self.db.addresses.update_one({"_id": replacement["_id"]}, {"$set": {"is_default": True, "updated_at": utc_now()}})
        return {"deleted": True, "id": str(address["_id"])}

    def set_default(self, user_id, address_id):
        address = self._get_owned(user_id, address_id)
        self.db.addresses.update_many({"user_id": address["user_id"]}, {"$set": {"is_default": False, "updated_at": utc_now()}})
        self.db.addresses.update_one({"_id": address["_id"]}, {"$set": {"is_default": True, "updated_at": utc_now()}})
        return serialize_doc(self.db.addresses.find_one({"_id": address["_id"]}))

    def _get_owned(self, user_id, address_id):
        address = self.db.addresses.find_one(
            {"_id": to_object_id(address_id, "address_id"), "user_id": to_object_id(user_id, "user_id")}
        )
        if not address:
            raise NotFoundError("收货地址不存在")
        return address

    def _validate(self, payload):
        name = (payload.get("name") or "").strip()
        phone = (payload.get("phone") or "").strip()
        address = (payload.get("address") or "").strip()
        errors = []
        if not name:
            errors.append({"field": "name", "message": "请填写收货人名称"})
        if len(phone) < 7 or len(phone) > 20:
            errors.append({"field": "phone", "message": "请填写有效手机号"})
        if not address:
            errors.append({"field": "address", "message": "请填写详细地址"})
        if errors:
            raise ValidationError("参数校验失败", errors)
        return {"name": name, "phone": phone, "address": address}


def build_user_summary(user, profile=None):
    profile = profile or {}
    profile_data = serialize_doc(profile) or {}
    if "avatar" not in profile_data:
        profile_data["avatar"] = profile_data.get("avatar_url", "")
    if "bio" not in profile_data:
        profile_data["bio"] = ""
    return {
        "id": str(user["_id"]),
        "phone": user.get("phone"),
        "roles": user.get("roles", []),
        "status": user.get("status"),
        "profile": profile_data,
    }


def _public_product(product, profile):
    return {
        "id": str(product["_id"]),
        "title": product.get("title"),
        "price": product.get("price"),
        "cover_image": product.get("cover_image"),
        "condition": product.get("condition"),
        "campus": product.get("campus") or profile.get("campus", ""),
        "status": product.get("status"),
        "created_at": product.get("created_at").isoformat() if product.get("created_at") else None,
        "view_count": product.get("view_count", 0),
        "favorite_count": product.get("favorite_count", 0),
        "seller": {
            "id": str(product.get("seller_id")),
            "nickname": profile.get("nickname", "校园用户"),
            "campus": profile.get("campus", ""),
        },
    }


def _public_reviews(db, user_id):
    items = list(db.reviews.find({"reviewee_id": user_id}).sort("created_at", -1).limit(50))
    return [_present_public_review(db, item) for item in items]


def _present_public_review(db, review):
    data = serialize_doc(review)
    reviewer_profile = db.user_profiles.find_one({"user_id": review["reviewer_id"]}) or {}
    data["reviewer"] = {
        "id": "" if review.get("anonymous") else str(review["reviewer_id"]),
        "nickname": "匿名用户" if review.get("anonymous") else reviewer_profile.get("nickname", "校园用户"),
        "avatar": "" if review.get("anonymous") else reviewer_profile.get("avatar") or reviewer_profile.get("avatar_url", ""),
    }
    return data


def _required_str(payload, field, message):
    value = (payload.get(field) or "").strip()
    if not value:
        raise ValidationError("参数校验失败", [{"field": field, "message": message}])
    return value
