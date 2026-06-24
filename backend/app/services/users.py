from datetime import datetime, timezone
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from ..adapters.wechat import WechatAuthAdapter
from ..domain.campus import is_allowed_campus, normalize_campus
from ..domain.categories import category_name, normalize_category_code
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError
from ..utils.images import normalize_image_list, normalize_image_url
from ..utils.jwt import create_token
from ..utils.serializers import serialize_doc, to_object_id
from .content_moderation import ContentModerationService
from .credit import CreditService, credit_level


def utc_now():
    return datetime.now(timezone.utc)


PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def _validate_phone(phone):
    value = (phone or "").strip()
    if not value:
        raise ValidationError("参数校验失败", [{"field": "phone", "message": "手机号不能为空"}])
    if not PHONE_RE.match(value):
        raise ValidationError("参数校验失败", [{"field": "phone", "message": "手机号格式不正确"}])
    return value


def _validate_optional_phone(phone, field="phone"):
    value = (phone or "").strip()
    if value and not PHONE_RE.match(value):
        raise ValidationError("参数校验失败", [{"field": field, "message": "手机号格式不正确"}])
    return value


class AuthService:
    def __init__(self, db):
        self.users = UserRepository(db)
        self.wechat = WechatAuthAdapter()

    def password_login(self, phone, password):
        phone = _validate_phone(phone)
        if not (password or "").strip():
            raise ValidationError("参数校验失败", [{"field": "password", "message": "密码不能为空"}])
        user = self.users.find_by_phone(phone)
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            raise UnauthorizedError("手机号或密码错误")
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")
        user = self.users.update_user(user["_id"], {"last_login_at": utc_now(), "updated_at": utc_now()})

        profile = self.users.ensure_profile(
            user["_id"],
            {
                "nickname": user.get("nickname", ""),
                "avatar_url": user.get("avatar_url", ""),
                "avatar": user.get("avatar_url", ""),
                "profile_completed": bool(user.get("profile_completed")),
                "identity_type": user.get("identity_type", ""),
                "campus": "",
                "student_no": "",
                "contact_phone": "",
                "contact_wechat": "",
                "verified_status": "unverified",
                "credit_score": 100,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        )
        token = create_token(user["_id"], user.get("roles", []))
        return {"token": token, "user": build_user_summary(user, profile)}

    def dev_test_login(self, account_key, enabled=False):
        if not enabled:
            raise NotFoundError("开发测试登录未启用")
        accounts = {
            "buyer_a": ("18800000002", "buyer123456"),
            "buyer_b": ("18800000003", "buyerb123456"),
            "admin": ("18800000000", "admin123456"),
        }
        if account_key not in accounts:
            raise ValidationError("参数校验失败", [{"field": "account", "message": "测试账号不存在"}])
        phone, password = accounts[account_key]
        return self.password_login(phone, password)

    def wechat_login(self, payload):
        session = self.wechat.code_to_session(payload.get("code"))
        openid = session.get("openid")
        if not openid:
            raise UnauthorizedError("微信登录失败，未获取 openid")
        openid = str(openid).strip()
        user = self.users.find_by_openid(openid)
        if not user:
            try:
                user = self.users.create_user(
                    {
                        "openid": openid,
                        "password_hash": "",
                        "roles": ["buyer", "seller"],
                        "status": "active",
                        "nickname": "",
                        "avatar_url": "",
                        "profile_completed": False,
                        "identity_type": "",
                        "last_login_at": utc_now(),
                        "created_at": utc_now(),
                        "updated_at": utc_now(),
                    },
                    {
                        "nickname": "",
                        "avatar_url": "",
                        "avatar": "",
                        "profile_completed": False,
                        "identity_type": "",
                        "campus": "",
                        "student_no": "",
                        "contact_phone": "",
                        "contact_wechat": "",
                        "verified_status": "unverified",
                        "credit_score": 100,
                        "created_at": utc_now(),
                        "updated_at": utc_now(),
                    },
                )
            except DuplicateKeyError:
                user = self.users.find_by_openid(openid)
                if not user:
                    raise
        else:
            user = self.users.update_user(
                user["_id"],
                {
                    "openid": openid,
                    "last_login_at": utc_now(),
                    "updated_at": utc_now(),
                },
            )
        if user.get("status") in {"frozen", "disabled"}:
            raise UnauthorizedError("账号已被禁用，请联系管理员")
        profile = self.users.ensure_profile(
            user["_id"],
            {
                "nickname": user.get("nickname", ""),
                "avatar_url": user.get("avatar_url", ""),
                "avatar": user.get("avatar_url", ""),
                "profile_completed": bool(user.get("profile_completed")),
                "identity_type": user.get("identity_type", ""),
                "campus": "",
                "student_no": "",
                "contact_phone": "",
                "contact_wechat": "",
                "verified_status": "unverified",
                "credit_score": 100,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        )
        token = create_token(user["_id"], user.get("roles", []))
        return {
            "token": token,
            "user": build_user_summary(user, profile),
            "need_bind_phone": not bool(user.get("phone")),
        }

    def register(self, payload):
        phone = _validate_phone(payload.get("phone"))
        password = _required_str(payload, "password", "密码不能为空")
        if len(password) < 6:
            raise ValidationError("参数校验失败", [{"field": "password", "message": "密码至少 6 位"}])
        if self.users.find_by_phone(phone):
            raise ConflictError("手机号已注册")
        nickname = (payload.get("nickname") or "校园用户").strip()
        openid = (payload.get("openid") or "").strip()
        user_doc = {
            "phone": phone,
            "password_hash": generate_password_hash(password),
            "roles": ["buyer", "seller"],
            "status": "active",
            "nickname": nickname,
            "avatar_url": "",
            "profile_completed": False,
            "identity_type": "custom",
            "last_login_at": utc_now(),
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        if openid:
            user_doc["openid"] = openid
        campus = (payload.get("campus") or "").strip()
        if campus and not is_allowed_campus(campus):
            raise ValidationError("参数校验失败", [{"field": "campus", "message": "校区只能选择东校区或西校区"}])
        user = self.users.create_user(
            user_doc,
            {
                "nickname": nickname,
                "avatar_url": "",
                "avatar": "",
                "profile_completed": False,
                "identity_type": "custom",
                "campus": campus,
                "student_no": "",
                "contact_phone": "",
                "contact_wechat": "",
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
        phone = _validate_phone(payload.get("phone"))
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
        self.credit = CreditService(db)

    def get_me(self, user_id):
        user = self.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        profile = self.users.ensure_profile(
            user_id,
            {
                "nickname": user.get("nickname", ""),
                "avatar_url": user.get("avatar_url", ""),
                "avatar": user.get("avatar_url", ""),
                "profile_completed": bool(user.get("profile_completed")),
                "identity_type": user.get("identity_type", ""),
                "campus": "",
                "student_no": "",
                "contact_phone": "",
                "contact_wechat": "",
                "verified_status": "unverified",
                "credit_score": 100,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        )
        summary = build_user_summary(user, profile)
        summary["stats"] = self._account_stats(user["_id"])
        summary["credit"] = self.credit.detail(user["_id"])
        return summary

    def update_me(self, user_id, payload):
        user = self.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        allowed = {
            "avatar",
            "avatar_url",
            "nickname",
            "campus",
            "bio",
            "contact_phone",
            "contact_wechat",
            "identity_type",
        }
        unknown = set(payload.keys()) - allowed
        if unknown:
            raise ValidationError("参数校验失败", [{"field": ",".join(sorted(unknown)), "message": "包含不允许的字段"}])
        fields = {}
        user_fields = {}
        if "avatar" in payload:
            fields["avatar"] = (payload.get("avatar") or "").strip()
            fields["avatar_url"] = fields["avatar"]
        if "avatar_url" in payload:
            fields["avatar_url"] = (payload.get("avatar_url") or "").strip()
            fields["avatar"] = fields["avatar_url"]
        if "avatar_url" in fields:
            user_fields["avatar_url"] = fields["avatar_url"]
        if "nickname" in payload:
            nickname = (payload.get("nickname") or "").strip()
            ContentModerationService(self.db).validate_fields(user_id, {"nickname": nickname})
            if len(nickname) < 1 or len(nickname) > 30:
                raise ValidationError("参数校验失败", [{"field": "nickname", "message": "昵称需为 1-30 字"}])
            fields["nickname"] = nickname
            user_fields["nickname"] = nickname
        if "identity_type" in payload:
            identity_type = (payload.get("identity_type") or "").strip()
            if identity_type not in {"wechat", "custom"}:
                raise ValidationError(
                    "参数校验失败",
                    [{"field": "identity_type", "message": "identity_type 只能是 wechat 或 custom"}],
                )
            if identity_type == "wechat" and (user.get("phone") or not user.get("openid")):
                raise ForbiddenError("手机号账号不能使用微信头像身份")
            fields["identity_type"] = identity_type
            user_fields["identity_type"] = identity_type
        if "campus" in payload:
            campus = (payload.get("campus") or "").strip()
            if campus and not is_allowed_campus(campus):
                raise ValidationError("参数校验失败", [{"field": "campus", "message": "校区只能选择东校区或西校区"}])
            fields["campus"] = campus
        if "bio" in payload:
            bio = (payload.get("bio") or "").strip()
            if len(bio) > 120:
                raise ValidationError("参数校验失败", [{"field": "bio", "message": "简介不能超过 120 字"}])
            fields["bio"] = bio
        if "contact_phone" in payload:
            fields["contact_phone"] = _validate_optional_phone(payload.get("contact_phone"), "contact_phone")
        if "contact_wechat" in payload:
            fields["contact_wechat"] = (payload.get("contact_wechat") or "").strip()
        current_profile = self.users.find_profile(user_id) or {}
        nickname_value = fields.get("nickname") or current_profile.get("nickname") or ""
        avatar_value = fields.get("avatar_url") or current_profile.get("avatar_url") or current_profile.get("avatar") or ""
        completed = bool(nickname_value.strip() and avatar_value.strip())
        fields["profile_completed"] = completed
        user_fields["profile_completed"] = completed
        fields["updated_at"] = utc_now()
        user_fields["updated_at"] = utc_now()
        if user_fields:
            self.users.update_user(user_id, user_fields)
        profile = self.users.update_profile(user_id, fields)
        user = self.users.find_by_id(user_id)
        summary = build_user_summary(user, profile)
        summary["stats"] = self._account_stats(user["_id"])
        summary["credit"] = self.credit.detail(user["_id"])
        return summary

    def get_credit(self, user_id):
        detail = self.credit.detail(user_id)
        detail["records"] = self.credit.records(user_id, {"page": 1, "page_size": 10})["items"]
        return detail

    def list_credit_records(self, user_id, args):
        return self.credit.records(user_id, args)

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
            "campus": normalize_campus(profile.get("campus"), ""),
            "bio": profile.get("bio", ""),
            "credit_score": safe_credit_score(profile.get("credit_score", 100)),
            "campus_verified": profile.get("verified_status") == "approved",
            "student_verified": bool(profile.get("student_verified")),
            "student_verify_status": profile.get("student_verify_status") or ("verified" if profile.get("student_verified") else "none"),
            "student_verify_status_text": student_verify_status_text(profile.get("student_verify_status") or ("verified" if profile.get("student_verified") else "none")),
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

    def search_users(self, args):
        keyword = (args.get("q") or args.get("keyword") or "").strip()
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        if not keyword:
            return {"items": [], "pagination": {"page": page, "page_size": page_size, "total": 0}}

        regex = {"$regex": re.escape(keyword), "$options": "i"}
        candidate_ids = set()
        user_query = {
            "status": {"$nin": ["frozen", "disabled", "banned"]},
            "$or": [
                {"nickname": regex},
                {"username": regex},
                {"phone": regex},
            ],
        }
        for user in self.db.users.find(user_query):
            candidate_ids.add(str(user["_id"]))

        profile_query = {
            "$or": [
                {"nickname": regex},
                {"campus": regex},
                {"school": regex},
                {"school_name": regex},
                {"real_name": regex},
            ]
        }
        for profile in self.db.user_profiles.find(profile_query):
            if profile.get("user_id"):
                candidate_ids.add(str(profile["user_id"]))

        users = []
        for user_id in candidate_ids:
            try:
                user = self.users.find_by_id(user_id)
            except Exception:
                user = None
            if not user or user.get("status") in {"frozen", "disabled", "banned"}:
                continue
            profile = self.users.find_profile(user["_id"]) or {}
            users.append(self._present_search_user(user, profile))
        users.sort(key=lambda item: (item["on_sale_count"], item.get("credit_score", 0)), reverse=True)
        total = len(users)
        start = (page - 1) * page_size
        return {"items": users[start:start + page_size], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def search_all(self, args, current_user=None):
        raw_query = (args.get("q") or args.get("keyword") or "").strip()
        search_type = (args.get("type") or "all").strip()
        ai_enabled = str(args.get("ai") or args.get("ai_search") or "").lower() in {"1", "true", "yes"}
        ai_info = (
            self._ai_semantic_product_recall(raw_query, args)
            if ai_enabled and raw_query and search_type in {"all", "product", "products"}
            else {"enabled": False, "used": False, "query": raw_query, "matched_product_ids": []}
        )

        if raw_query and current_user and current_user.get("_id"):
            self._record_search(current_user["_id"], raw_query, ai_info)

        products = self._search_products_with_semantic_recall(args, raw_query, ai_info, current_user)

        users = self.search_users({**dict(args), "q": raw_query})
        return {
            "type": search_type,
            "query": raw_query,
            "effective_query": raw_query,
            "ai_search": ai_info,
            "products": products if search_type in {"all", "product", "products"} else {"items": [], "pagination": {"page": 1, "page_size": 20, "total": 0}},
            "users": users if search_type in {"all", "user", "users"} else {"items": [], "pagination": {"page": 1, "page_size": 20, "total": 0}},
        }

    def search_meta(self, current_user=None):
        if not current_user or not current_user.get("_id"):
            return {"history": [], "common_bought": [], "common_viewed": []}
        user_id = current_user["_id"]
        history = [item.get("keyword") for item in self.db.search_histories.find({"user_id": user_id}).sort("updated_at", -1).limit(12) if item.get("keyword")]
        return {
            "history": _unique_keep_order(history)[:12],
            "common_bought": self._common_bought_terms(user_id),
            "common_viewed": self._common_viewed_terms(user_id),
        }


    def clear_search_history(self, user_id):
        result = self.db.search_histories.delete_many({"user_id": ObjectId(str(user_id))})
        return {"cleared": True, "deleted_count": getattr(result, "deleted_count", 0)}

    def _record_search(self, user_id, keyword, ai_info=None):
        word = (keyword or "").strip()[:60]
        if not word:
            return
        now = utc_now()
        self.db.search_histories.update_one(
            {"user_id": ObjectId(str(user_id)), "keyword": word},
            {
                "$set": {
                    "user_id": ObjectId(str(user_id)),
                    "keyword": word,
                    "ai_used": bool((ai_info or {}).get("used")),
                    "updated_at": now,
                },
                "$inc": {"count": 1},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def _common_viewed_terms(self, user_id):
        rows = list(self.db.product_views.find({"user_id": ObjectId(str(user_id))}).sort("viewed_at", -1).limit(40))
        product_ids = [row.get("product_id") for row in rows if row.get("product_id")]
        return self._terms_from_products(product_ids)[:10]

    def _common_bought_terms(self, user_id):
        orders = list(self.db.orders.find({"buyer_id": ObjectId(str(user_id)), "status": {"$in": ["completed", "pending_review", "pending_receive", "pending_delivery"]}}).sort("created_at", -1).limit(30))
        product_ids = [order.get("product_id") for order in orders if order.get("product_id")]
        for order in orders:
            for item in self.db.order_items.find({"order_id": order.get("_id")}):
                if item.get("product_id"):
                    product_ids.append(item.get("product_id"))
                snapshot = item.get("product_snapshot") or {}
                if snapshot.get("title"):
                    product_ids.append({"title": snapshot.get("title"), "category_name": snapshot.get("category_name")})
        return self._terms_from_products(product_ids)[:10]

    def _terms_from_products(self, product_refs):
        terms = []
        for ref in product_refs:
            product = ref if isinstance(ref, dict) else self.products.find_by_id(ref)
            if not product:
                continue
            category_text = product.get("category_name") or (category_name(product.get("category")) if product.get("category") else "")
            title = (product.get("title") or "").strip()
            for item in [category_text, _short_product_term(title), title[:12]]:
                item = (item or "").strip()
                if item and item not in terms:
                    terms.append(item)
        return terms

    def _search_products_with_semantic_recall(self, args, raw_query, ai_info, current_user=None):
        from .products import ProductService

        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        filters = self._product_search_filters(args, keyword=raw_query)
        normal_items = self.products.list_public_all(filters) if raw_query else []
        normal_ids = {str(item["_id"]) for item in normal_items}
        matched_ids = [str(item) for item in ai_info.get("matched_product_ids") or []]
        ai_items = self._products_by_ids(matched_ids)

        merged = {}
        source_map = {}
        for item in normal_items:
            key = str(item["_id"])
            merged[key] = item
            source_map[key] = {"keyword": True, "ai": False}
        for item in ai_items:
            key = str(item["_id"])
            if key not in merged:
                merged[key] = item
                source_map[key] = {"keyword": False, "ai": True}
            else:
                source_map[key]["ai"] = True

        items = list(merged.values())
        items.sort(key=lambda item: self._search_product_sort_key(item, raw_query, source_map.get(str(item["_id"]), {})), reverse=True)
        total = len(items)
        page_items = items[(page - 1) * page_size : page * page_size]
        presenter = ProductService(self.db)
        presented = []
        for item in page_items:
            data = presenter._present(item, current_user, compact=True)
            source = source_map.get(str(item["_id"]), {})
            data["search_match_type"] = "keyword_ai" if source.get("keyword") and source.get("ai") else ("ai" if source.get("ai") else "keyword")
            data["ai_semantic_match"] = bool(source.get("ai") and str(item["_id"]) not in normal_ids)
            presented.append(data)
        return {
            "items": presented,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def _product_search_filters(self, args, keyword=""):
        filters = {
            "keyword": (keyword or "").strip(),
            "condition": (args.get("condition") or "").strip(),
            "category_id": None,
            "category": normalize_category_code(args.get("category") or args.get("category_code")),
            "campus": (args.get("campus") or "").strip(),
            "sort": "newest",
        }
        if args.get("category_id"):
            try:
                filters["category_id"] = to_object_id(args.get("category_id"), "category_id")
            except Exception:
                filters["category_id"] = None
        for source_key, target_key in [("min_price", "min_price"), ("max_price", "max_price")]:
            value = args.get(source_key)
            if value not in (None, ""):
                try:
                    filters[target_key] = float(value)
                except (TypeError, ValueError):
                    pass
        return filters

    def _search_product_sort_key(self, item, query, source):
        title = str(item.get("title") or "")
        keyword = str(query or "").strip()
        title_exact = bool(keyword and keyword.lower() == title.lower())
        title_contains = bool(keyword and keyword.lower() in title.lower())
        keyword_match = bool(source.get("keyword"))
        ai_match = bool(source.get("ai"))
        created_at = item.get("created_at")
        timestamp = created_at.timestamp() if hasattr(created_at, "timestamp") else 0
        return (
            4 if title_exact else 0,
            3 if title_contains else 0,
            2 if keyword_match else 0,
            1 if ai_match else 0,
            int(item.get("view_count", 0) or 0),
            int(item.get("favorite_count", 0) or 0),
            timestamp,
        )

    def _products_by_ids(self, product_ids):
        object_ids = []
        seen = set()
        for value in product_ids:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            try:
                object_ids.append(ObjectId(text))
                seen.add(text)
            except Exception:
                continue
        if not object_ids:
            return []
        query = {
            "_id": {"$in": object_ids},
            "status": {"$in": ["on_sale", "active"]},
            "deleted_at": {"$exists": False},
            "stock": {"$gt": 0},
        }
        docs = list(self.db.products.find(query))
        order = {str(item): index for index, item in enumerate(object_ids)}
        docs.sort(key=lambda item: order.get(str(item["_id"]), 999999))
        return docs

    def _ai_semantic_product_recall(self, query, args):
        enabled = os.getenv("AI_SEARCH_ENABLED", "false").lower() == "true"
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not enabled:
            return {"enabled": False, "used": False, "query": query, "matched_product_ids": [], "message": "AI智搜未启用"}
        if not api_key:
            return {"enabled": True, "used": False, "query": query, "matched_product_ids": [], "message": "AI智搜未配置 DASHSCOPE_API_KEY"}
        candidates = self._semantic_product_candidates(args)
        if not candidates:
            return {"enabled": True, "used": False, "query": query, "matched_product_ids": [], "message": "没有可供 AI 智搜召回的在售商品"}
        try:
            return self._dashscope_semantic_product_recall(query, candidates, api_key)
        except Exception as exc:
            return {"enabled": True, "used": False, "query": query, "matched_product_ids": [], "message": f"AI智搜失败，已使用普通搜索：{exc}"}

    def _semantic_product_candidates(self, args, limit=80):
        filters = self._product_search_filters(args, keyword="")
        candidates = self.products.list_public_all(filters)
        candidates.sort(
            key=lambda item: (
                int(item.get("view_count", 0) or 0),
                int(item.get("favorite_count", 0) or 0),
                item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        result = []
        for item in candidates[:limit]:
            code = normalize_category_code(item.get("category")) or "other"
            result.append(
                {
                    "id": str(item["_id"]),
                    "title": item.get("title") or "",
                    "description": item.get("description") or "",
                    "category": code,
                    "category_name": item.get("category_name") or category_name(code),
                    "tags": item.get("tags") or [],
                    "price": item.get("price"),
                    "status": item.get("status"),
                }
            )
        return result

    def _dashscope_semantic_product_recall(self, query, candidates, api_key):
        base_url = os.getenv("AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
        model = (os.getenv("AI_SEARCH_MODEL") or os.getenv("QWEN_MODEL") or os.getenv("AI_MODEL") or "qwen-plus").strip()
        timeout_seconds = int(os.getenv("AI_TIMEOUT_SECONDS", "30") or 30)
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        prompt = (
            "你是校园二手交易平台的搜索理解助手。用户会输入一个搜索词，系统会提供当前数据库中的在售商品候选列表。"
            "请根据用户搜索意图，只从候选商品列表中选择相关商品。你只能返回候选商品里存在的 id，不能编造商品，不能生成候选列表以外的商品名。"
            "AI 不能只做关键词包含判断，要根据候选商品的 title、description、category、category_name、tags 综合判断语义相关性。"
            "如果商品标题本身是具有公众认知的卡通形象、角色、物品名称，可以根据常识判断其外观、颜色、用途、类别。"
            "只返回 JSON，不要 Markdown，不要解释文本。\n"
            '返回格式：{"matched_product_ids":[],"reason":""}\n'
            f"用户搜索词：{query[:120]}\n"
            f"候选商品列表：{json.dumps(candidates, ensure_ascii=False)}"
        )
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你只输出合法 JSON 对象，不输出 Markdown。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        request = Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DashScope HTTP {exc.code}: {detail[:120]}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"DashScope connection failed: {exc}") from exc
        content_text = response_data["choices"][0]["message"]["content"]
        text = str(content_text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        candidate_ids = {str(item["id"]) for item in candidates}
        matched_ids = []
        for item in parsed.get("matched_product_ids") or []:
            product_id = str(item).strip()
            if product_id in candidate_ids and product_id not in matched_ids:
                matched_ids.append(product_id)
        return {
            "enabled": True,
            "used": True,
            "query": query,
            "matched_product_ids": matched_ids,
            "reason": str(parsed.get("reason") or "").strip()[:200],
            "candidate_count": len(candidates),
            "message": "AI智搜已启用",
        }

    def _present_search_user(self, user, profile):
        status = profile.get("student_verify_status") or ("verified" if profile.get("student_verified") else "none")
        return {
            "user_id": str(user["_id"]),
            "id": str(user["_id"]),
            "nickname": profile.get("nickname") or user.get("nickname") or "校园用户",
            "avatar_url": normalize_image_url(profile.get("avatar_url") or profile.get("avatar") or user.get("avatar_url") or ""),
            "campus": normalize_campus(profile.get("campus"), ""),
            "credit_score": safe_credit_score(profile.get("credit_score", 100)),
            "student_verify_status": status,
            "student_verify_status_text": student_verify_status_text(status),
            "on_sale_count": self.db.products.count_documents({"seller_id": user["_id"], "status": "on_sale", "deleted_at": {"$exists": False}}),
        }

    def cancel_account(self, user_id):
        user = self.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        object_id = user["_id"]
        active_order_count = self.db.orders.count_documents(
            {
                "$or": [{"buyer_id": object_id}, {"seller_id": object_id}],
                "status": {"$in": ["pending_payment", "pending_delivery", "pending_receive", "refunding"]},
            }
        )
        active_refund_count = self.db.refunds.count_documents(
            {
                "$or": [{"buyer_id": object_id}, {"seller_id": object_id}],
                "status": {"$in": ["requested", "seller_agreed", "refunding", "seller_rejected"]},
            }
        )
        if active_order_count or active_refund_count:
            raise ConflictError("存在未完成订单或售后，暂不能注销账号")

        now = utc_now()
        self.db.users.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "disabled",
                    "cancelled_at": now,
                    "updated_at": now,
                    "nickname": "已注销用户",
                    "avatar_url": "",
                    "profile_completed": False,
                },
                "$unset": {"phone": "", "openid": "", "password_hash": ""},
            },
        )
        self.db.user_profiles.update_one(
            {"user_id": object_id},
            {
                "$set": {
                    "nickname": "已注销用户",
                    "avatar": "",
                    "avatar_url": "",
                    "bio": "",
                    "contact_phone": "",
                    "contact_wechat": "",
                    "profile_completed": False,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        return {"cancelled": True, "id": str(object_id)}

    def _account_stats(self, user_id):
        object_id = user_id if isinstance(user_id, ObjectId) else to_object_id(user_id, "user_id")
        return {
            "published": self.db.products.count_documents({"seller_id": object_id, "deleted_at": {"$exists": False}}),
            "bought": self.db.orders.count_documents({"buyer_id": object_id}),
            "sold": self.db.orders.count_documents({"seller_id": object_id}),
            "favorites": self.db.favorites.count_documents({"user_id": object_id}),
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
        if not PHONE_RE.match(phone):
            errors.append({"field": "phone", "message": "手机号格式不正确"})
        if not address:
            errors.append({"field": "address", "message": "请填写详细地址"})
        if errors:
            raise ValidationError("参数校验失败", errors)
        return {"name": name, "phone": phone, "address": address}




def _unique_keep_order(values):
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _short_product_term(title):
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", str(title or "")).strip()
    parts = [part for part in text.split() if part]
    if not parts:
        return ""
    if len(parts[0]) >= 2:
        return parts[0][:12]
    return ""


def safe_credit_score(value, default=100):
    if value is None or value == "":
        return default
    try:
        score = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))

def build_user_summary(user, profile=None):
    profile = profile or {}
    profile_data = serialize_doc(profile) or {}
    nickname = profile_data.get("nickname") or user.get("nickname") or ""
    avatar_url = normalize_image_url(profile_data.get("avatar_url") or profile_data.get("avatar") or user.get("avatar_url") or "")
    identity_type = profile_data.get("identity_type") or user.get("identity_type") or ""
    profile_completed = bool(nickname.strip() and avatar_url.strip())
    profile_data["nickname"] = nickname
    profile_data["avatar_url"] = avatar_url
    profile_data["profile_completed"] = profile_completed
    profile_data["identity_type"] = identity_type
    if not profile_data.get("avatar"):
        profile_data["avatar"] = avatar_url
    if "bio" not in profile_data:
        profile_data["bio"] = ""
    profile_data["campus"] = normalize_campus(profile_data.get("campus"), "")
    credit_score = safe_credit_score(profile_data.get("credit_score", 100))
    profile_data["credit_score"] = credit_score
    profile_data["credit_level"] = credit_level(credit_score)
    student_status = profile_data.get("student_verify_status") or ("verified" if profile_data.get("student_verified") else "none")
    profile_data["student_verified"] = student_status in {"verified", "approved"}
    profile_data["student_verify_status"] = "verified" if student_status == "approved" else student_status
    profile_data["student_verify_status_text"] = student_verify_status_text(student_status)
    return {
        "id": str(user["_id"]),
        "openid_mask": _mask_openid(user.get("openid")),
        "phone": user.get("phone"),
        "roles": user.get("roles", []),
        "status": user.get("status"),
        "nickname": nickname,
        "avatar_url": avatar_url,
        "profile_completed": profile_completed,
        "identity_type": identity_type,
        "credit_score": credit_score,
        "credit_level": profile_data["credit_level"],
        "student_verified": profile_data["student_verified"],
        "student_verify_status": profile_data["student_verify_status"],
        "student_verify_status_text": profile_data["student_verify_status_text"],
        "last_login_at": user.get("last_login_at").isoformat() if user.get("last_login_at") else None,
        "profile": profile_data,
    }


def student_verify_status_text(status):
    return {
        "none": "未认证",
        "pending": "认证审核中",
        "verified": "已认证",
        "approved": "已认证",
        "rejected": "认证未通过",
    }.get(status or "none", "未认证")


def _mask_openid(openid):
    if not openid:
        return ""
    openid = str(openid)
    if len(openid) <= 8:
        return f"{openid[:2]}***{openid[-2:]}"
    return f"{openid[:6]}***{openid[-4:]}"


def _public_product(product, profile):
    return {
        "id": str(product["_id"]),
        "title": product.get("title"),
        "price": product.get("price"),
        "cover_image": normalize_image_url(product.get("cover_image")) or (normalize_image_list(product.get("images") or [])[:1] or [""])[0],
        "images": normalize_image_list(product.get("images") or []),
        "condition": product.get("condition"),
        "campus": normalize_campus(product.get("campus") or profile.get("campus"), ""),
        "status": product.get("status"),
        "created_at": product.get("created_at").isoformat() if product.get("created_at") else None,
        "view_count": product.get("view_count", 0),
        "favorite_count": product.get("favorite_count", 0),
        "seller": {
            "id": str(product.get("seller_id")),
            "nickname": profile.get("nickname", "校园用户"),
            "campus": normalize_campus(profile.get("campus"), ""),
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
