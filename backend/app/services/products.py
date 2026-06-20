from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from bson import ObjectId
from ..domain.campus import is_allowed_campus, normalize_campus
from ..domain.categories import CATEGORY_CODES, category_name, classify_category, normalize_category_code
from ..repositories.categories import CategoryRepository
from ..repositories.logs import OperationLogRepository
from ..repositories.products import ProductRepository, utc_now
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.images import normalize_image_list, normalize_image_url
from ..utils.serializers import serialize_doc, to_object_id


PRODUCT_STATUSES = {"draft", "pending_review", "rejected", "on_sale", "locked", "sold", "off_shelf"}
EDITABLE_STATUSES = {"draft", "rejected", "off_shelf", "on_sale"}
CONDITIONS = {"new", "like_new", "good", "fair"}


class ProductService:
    def __init__(self, db):
        self.db = db
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)
        self.users = UserRepository(db)
        self.operation_logs = OperationLogRepository(db)

    def list_products(self, args, current_user=None):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 10)), 1), 50)
        mode = (args.get("mode") or "latest").strip()
        if mode == "newest":
            mode = "latest"
        filters = {
            "keyword": args.get("keyword", "").strip(),
            "condition": args.get("condition", "").strip(),
            "category_id": None,
            "category": normalize_category_code(args.get("category") or args.get("category_code")),
            "min_price": _optional_float(args.get("min_price"), "min_price"),
            "max_price": _optional_float(args.get("max_price"), "max_price"),
            "campus": (args.get("campus") or "").strip(),
            "sort": (args.get("sort") or "newest").strip(),
            "mode": mode,
            "date_from": _optional_date(args.get("date_from"), "date_from", end=False),
            "date_to": _optional_date(args.get("date_to"), "date_to", end=True),
        }
        if args.get("category_id"):
            filters["category_id"] = to_object_id(args.get("category_id"), "category_id")
            if not filters["category"]:
                category_doc = self.categories.find_by_id(filters["category_id"])
                filters["category"] = normalize_category_code((category_doc or {}).get("code"))
        if filters["category"] and filters["category"] not in CATEGORY_CODES:
            raise ValidationError("参数校验失败", [{"field": "category", "message": "分类不合法"}])
        if filters["mode"] not in {"recommend", "latest", "hot"}:
            raise ValidationError("参数校验失败", [{"field": "mode", "message": "展示模式不合法"}])
        if filters["condition"] and filters["condition"] not in CONDITIONS:
            raise ValidationError("参数校验失败", [{"field": "condition", "message": "成色不合法"}])
        if filters["campus"] and not is_allowed_campus(filters["campus"]):
            raise ValidationError("参数校验失败", [{"field": "campus", "message": "校区只能选择东校区或西校区"}])
        if filters["sort"] not in {"newest", "price_asc", "price_desc", "hot"}:
            raise ValidationError("参数校验失败", [{"field": "sort", "message": "排序方式不合法"}])

        if mode == "recommend":
            items, total = self._list_recommended(filters, page, page_size, current_user)
        else:
            filters["sort"] = "hot" if mode == "hot" else "newest"
            items, total = self.products.list_public(filters, page, page_size)
        return {
            "items": [self._present(item, current_user, compact=True) for item in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def list_recommendations(self, product_id, current_user=None, limit=6):
        product = self._get_existing(product_id)
        if product.get("status") != "on_sale":
            return {"items": []}
        limit = min(max(int(limit or 6), 1), 20)
        category = normalize_category_code(product.get("category"))
        filters = {
            "category": category,
            "exclude_product_id": product["_id"],
            "campus": product.get("campus") or "",
            "sort": "hot",
        }
        candidates = self.products.list_public_all(filters)
        if len(candidates) < limit:
            fallback_filters = {
                "category": category,
                "exclude_product_id": product["_id"],
                "sort": "hot",
            }
            seen = {item["_id"] for item in candidates}
            candidates.extend([item for item in self.products.list_public_all(fallback_filters) if item["_id"] not in seen])
        if len(candidates) < limit:
            seen = {item["_id"] for item in candidates}
            candidates.extend([
                item
                for item in self.products.list_public_all({"exclude_product_id": product["_id"], "sort": "hot"})
                if item["_id"] not in seen
            ])

        base_price = float(product.get("price") or 0)
        def score(item):
            price_gap = abs(float(item.get("price") or 0) - base_price)
            same_category = normalize_category_code(item.get("category")) == category
            same_campus = item.get("campus") and item.get("campus") == product.get("campus")
            return (
                100 if same_category else 0,
                30 if same_campus else 0,
                -price_gap,
                int(item.get("view_count", 0) or 0) + int(item.get("favorite_count", 0) or 0) * 3,
                item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            )

        candidates.sort(key=score, reverse=True)
        return {"items": [self._present(item, current_user, compact=True) for item in candidates[:limit]]}

    def _list_recommended(self, filters, page, page_size, current_user=None):
        user_id = ObjectId(str(current_user["_id"])) if current_user and current_user.get("_id") else None
        query_filters = {**filters}
        items = self.products.list_public_all(query_filters)

        preferences = self._recommendation_preferences(user_id) if user_id else {
            "top_viewed_categories": set(),
            "favorite_categories": set(),
            "bought_categories": set(),
        }
        scored = []
        for item in items:
            item["recommendation_score"] = self._recommendation_score(item, user_id, preferences)
            scored.append(item)
        scored.sort(
            key=lambda item: (
                float(item.get("recommendation_score", 0) or 0),
                item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        total = len(scored)
        return scored[(page - 1) * page_size : page * page_size], total

    def _recommendation_preferences(self, user_id):
        viewed_counts = {}
        for view in self.db.product_views.find({"user_id": user_id}):
            category_id = view.get("category_id")
            if category_id:
                viewed_counts[category_id] = viewed_counts.get(category_id, 0) + 1
        max_view_count = max(viewed_counts.values(), default=0)
        top_viewed_categories = {
            category_id for category_id, count in viewed_counts.items() if count == max_view_count and count > 0
        }

        favorite_categories = set()
        for favorite in self.db.favorites.find({"user_id": user_id}):
            product = self.products.find_by_id(favorite.get("product_id"))
            if product and product.get("category_id"):
                favorite_categories.add(product["category_id"])

        bought_categories = set()
        for order in self.db.orders.find({"buyer_id": user_id}):
            product = self.products.find_by_id(order.get("product_id"))
            if product and product.get("category_id"):
                bought_categories.add(product["category_id"])
            for snapshot in order.get("items", []):
                category_id = (snapshot.get("product_snapshot") or {}).get("category_id")
                if category_id:
                    bought_categories.add(category_id)

        return {
            "top_viewed_categories": top_viewed_categories,
            "favorite_categories": favorite_categories,
            "bought_categories": bought_categories,
        }

    def _recommendation_score(self, product, user_id, preferences):
        score = 10.0
        category_id = product.get("category_id")
        if category_id in preferences["top_viewed_categories"]:
            score += 30
        if category_id in preferences["favorite_categories"]:
            score += 25
        if category_id in preferences["bought_categories"]:
            score += 35

        score += min(int(product.get("view_count", 0) or 0), 100) * 0.2
        score += int(product.get("favorite_count", 0) or 0) * 2

        created_at = product.get("created_at")
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = utc_now() - created_at
            if age <= timedelta(days=7):
                score += 10
            if age <= timedelta(days=1):
                score += 10

        return round(score, 2)

    def list_my_products(self, user_id, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        status = (args.get("status") or "").strip()
        if status and status not in PRODUCT_STATUSES:
            raise ValidationError("参数校验失败", [{"field": "status", "message": "商品状态不合法"}])
        items, total = self.products.list_mine(ObjectId(str(user_id)), status=status or None, page=page, page_size=page_size)
        current_user = {"_id": ObjectId(str(user_id)), "roles": []}
        return {
            "items": [self._present(item, current_user, compact=True) for item in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def list_admin_products(self, args, admin_user):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        status = (args.get("status") or "pending_review").strip()
        if status not in PRODUCT_STATUSES:
            raise ValidationError("参数校验失败", [{"field": "status", "message": "商品状态不合法"}])
        items, total = self.products.list_admin(status=status, page=page, page_size=page_size)
        return {
            "items": [self._present(item, admin_user, compact=False) for item in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def get_product(self, product_id, current_user=None):
        product = self._get_existing(product_id)
        if not self._can_view(product, current_user):
            raise NotFoundError("商品不存在或不可见")
        if product.get("status") == "on_sale":
            product = self.products.increment_view_count(product["_id"])
            if current_user and current_user.get("_id"):
                self._record_product_view(current_user["_id"], product)
        return self._present(product, current_user)

    def create_product(self, user_id, payload):
        self._reject_client_status(payload)
        submit_action = payload.get("submit_action", "draft")
        status = "pending_review" if submit_action == "review" else "draft"
        if submit_action not in {"draft", "review"}:
            raise ValidationError("参数校验失败", [{"field": "submit_action", "message": "提交动作不合法"}])
        data = self._validate_product_payload(payload, partial=submit_action == "draft")

        product = {
            "title": "",
            "description": "",
            "price": None,
            "category_id": None,
            "category": "other",
            "category_name": category_name("other"),
            "category_source": "auto",
            "condition": "",
            "stock": 1,
            "images": [],
            "cover_image": "",
            "campus": "",
            "delivery_options": ["meetup"],
            **data,
            "seller_id": ObjectId(str(user_id)),
            "status": status,
            "review": {"reason": "", "audited_by": None, "audited_at": None},
            "sold_count": 0,
        }
        created = self.products.create(product)
        if submit_action == "review":
            self._ensure_review_ready(created)
        return self._present(created, {"_id": ObjectId(str(user_id)), "roles": []})

    def update_product(self, product_id, user_id, payload):
        self._reject_client_status(payload)
        product = self._get_existing(product_id)
        self._ensure_owner(product, user_id)
        if product["status"] not in EDITABLE_STATUSES:
            raise ConflictError("当前商品状态不允许编辑")

        data = self._validate_product_payload(payload, partial=True)
        if not data:
            raise ValidationError("参数校验失败", [{"field": "body", "message": "没有可更新字段"}])
        updated = self.products.update_fields(product["_id"], data)
        return self._present(updated, {"_id": ObjectId(str(user_id)), "roles": []})

    def submit_review(self, product_id, user_id):
        product = self._get_existing(product_id)
        self._ensure_owner(product, user_id)
        if product["status"] not in {"draft", "rejected", "off_shelf"}:
            raise ConflictError("当前商品状态不允许提交审核")
        self._ensure_review_ready(product)
        updated = self.products.update_fields(product["_id"], {"status": "pending_review"})
        return self._present(updated, {"_id": ObjectId(str(user_id)), "roles": []})

    def audit_product(self, product_id, admin_user, payload, trace_id=None):
        product = self._get_existing(product_id)
        if product["status"] != "pending_review":
            raise ConflictError("只有待审核商品可以审核")

        result = payload.get("result")
        reason = (payload.get("reason") or "").strip()
        if result not in {"approved", "rejected"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "审核结果不合法"}])
        if result == "rejected" and not reason:
            raise ValidationError("参数校验失败", [{"field": "reason", "message": "驳回时必须填写原因"}])

        new_status = "on_sale" if result == "approved" else "rejected"
        updated = self.products.update_fields(
            product["_id"],
            {
                "status": new_status,
                "review": {
                    "result": result,
                    "reason": reason,
                    "audited_by": admin_user["_id"],
                    "audited_at": utc_now(),
                },
            },
        )
        self.operation_logs.create(
            actor_id=admin_user["_id"],
            action="product_audit",
            target_type="product",
            target_id=product["_id"],
            detail={"result": result, "reason": reason},
            trace_id=trace_id,
        )
        return self._present(updated, admin_user)

    def off_shelf(self, product_id, current_user, payload=None, trace_id=None):
        product = self._get_existing(product_id)
        is_admin = "admin" in current_user.get("roles", [])
        if not is_admin:
            self._ensure_owner(product, current_user["_id"])
        if product["status"] != "on_sale":
            raise ConflictError("只有在售商品可以下架")

        reason = ((payload or {}).get("reason") or "").strip()
        updated = self.products.update_fields(product["_id"], {"status": "off_shelf"})
        if is_admin:
            self.operation_logs.create(
                actor_id=current_user["_id"],
                action="product_force_off_shelf",
                target_type="product",
                target_id=product["_id"],
                detail={"reason": reason},
                trace_id=trace_id,
            )
        return self._present(updated, current_user)

    def delete_product(self, product_id, user_id):
        product = self._get_existing(product_id)
        self._ensure_owner(product, user_id)
        if product["status"] not in {"sold", "off_shelf"}:
            raise ConflictError("只有已售出或已下架商品可以删除")
        self.products.update_fields(product["_id"], {"deleted_at": utc_now()})
        return {"deleted": True, "id": str(product["_id"])}

    def republish_product(self, product_id, user_id):
        product = self._get_existing(product_id)
        self._ensure_owner(product, user_id)
        if product["status"] not in {"sold", "off_shelf"}:
            raise ConflictError("只有已售出或已下架商品可以重新发布")
        stock = max(int(product.get("stock", 0) or 0), 1)
        self._ensure_review_ready({**product, "stock": stock})
        updated = self.products.update_fields(
            product["_id"],
            {
                "status": "pending_review",
                "stock": stock,
                "review": {"result": "", "reason": "", "audited_by": None, "audited_at": None},
            },
        )
        return self._present(updated, {"_id": ObjectId(str(user_id)), "roles": []})

    def _get_existing(self, product_id):
        product = self.products.find_by_id(to_object_id(product_id, "product_id"))
        if not product or product.get("deleted_at"):
            raise NotFoundError("商品不存在")
        return product

    def _validate_product_payload(self, payload, partial=False):
        errors = []
        data = {}
        fields = {
            "title",
            "description",
            "price",
            "category_id",
            "category",
            "category_name",
            "category_source",
            "condition",
            "stock",
            "images",
            "cover_image",
            "campus",
            "delivery_options",
        }
        unknown = set(payload.keys()) - fields - {"submit_action", "idempotency_key"}
        if unknown:
            errors.append({"field": ",".join(sorted(unknown)), "message": "包含不允许的字段"})

        def need(name):
            return not partial or name in payload

        if need("title"):
            title = (payload.get("title") or "").strip()
            if len(title) < 2 or len(title) > 50:
                errors.append({"field": "title", "message": "标题长度需为 2-50 字"})
            else:
                data["title"] = title

        if need("description"):
            description = (payload.get("description") or "").strip()
            if not description and not partial:
                errors.append({"field": "description", "message": "商品描述不能为空"})
            else:
                data["description"] = description

        if need("price"):
            price = _required_float(payload.get("price"), "price", errors)
            if price is not None:
                data["price"] = price

        if any(key in payload for key in ["category", "category_id"]) or (not partial and "category" not in data):
            self._apply_category_payload(payload, data, errors)

        if "condition" in payload:
            condition = (payload.get("condition") or "").strip()
            if condition and condition not in CONDITIONS:
                errors.append({"field": "condition", "message": "成色不合法"})
            else:
                data["condition"] = condition

        if need("stock"):
            stock = payload.get("stock")
            if not isinstance(stock, int) or stock < 0:
                errors.append({"field": "stock", "message": "库存必须是非负整数"})
            else:
                data["stock"] = stock

        if "images" in payload or not partial:
            images = payload.get("images") or []
            if not isinstance(images, list) or len(images) > 9:
                errors.append({"field": "images", "message": "图片最多 9 张"})
            else:
                data["images"] = images
                data["cover_image"] = payload.get("cover_image") or (images[0] if images else "")

        if "cover_image" in payload and "images" not in payload:
            data["cover_image"] = payload.get("cover_image") or ""
        if "campus" in payload or not partial:
            campus = (payload.get("campus") or "").strip()
            if not campus and not partial:
                errors.append({"field": "campus", "message": "请选择校区"})
            elif campus and not is_allowed_campus(campus):
                errors.append({"field": "campus", "message": "校区只能选择东校区或西校区"})
            else:
                data["campus"] = campus
        if "delivery_options" in payload or not partial:
            options = payload.get("delivery_options") or ["meetup"]
            if not isinstance(options, list) or not options:
                errors.append({"field": "delivery_options", "message": "交付方式不能为空"})
            else:
                data["delivery_options"] = options

        if errors:
            raise ValidationError("参数校验失败", errors)
        if not data.get("category") and not partial:
            inferred = classify_category(data.get("title", payload.get("title")), data.get("description", payload.get("description")))
            data["category"] = inferred
            data["category_name"] = category_name(inferred)
            data["category_source"] = "auto"
        return data

    def _apply_category_payload(self, payload, data, errors):
        category_doc = None
        category_code = normalize_category_code(payload.get("category"))
        source = (payload.get("category_source") or "").strip()
        raw_category_id = payload.get("category_id")
        if raw_category_id:
            category_id = to_object_id(raw_category_id, "category_id")
            category_doc = self.categories.find_by_id(category_id)
            if not category_doc:
                errors.append({"field": "category_id", "message": "分类不存在或已停用"})
                return
            category_code = normalize_category_code(category_doc.get("code")) or category_code
            data["category_id"] = category_id
        elif category_code:
            category_doc = self.categories.find_by_code(category_code)
            if category_doc:
                data["category_id"] = category_doc["_id"]
        else:
            inferred = classify_category(payload.get("title"), payload.get("description"))
            category_code = inferred
            source = "auto"

        if not category_code:
            category_code = "other"
        if category_code not in CATEGORY_CODES:
            errors.append({"field": "category", "message": "分类不合法"})
            return
        data["category"] = category_code
        data["category_name"] = category_name(category_code)
        data["category_source"] = "manual" if source == "manual" or raw_category_id else "auto"

    def _ensure_review_ready(self, product):
        missing = []
        for field in ["title", "description", "price", "campus"]:
            if not product.get(field):
                missing.append(field)
        if product.get("stock", 0) <= 0:
            missing.append("stock")
        if missing:
            raise ValidationError(
                "商品信息不完整，无法提交审核",
                [{"field": field, "message": "提交审核前必须填写"} for field in missing],
            )

    def _reject_client_status(self, payload):
        if "status" in payload:
            raise ValidationError("参数校验失败", [{"field": "status", "message": "商品状态由后端控制"}])

    def _ensure_owner(self, product, user_id):
        if str(product.get("seller_id")) != str(user_id):
            raise ForbiddenError("非本人不能操作该商品")

    def _can_view(self, product, current_user):
        if product["status"] == "on_sale":
            return True
        if not current_user:
            return False
        if "admin" in current_user.get("roles", []):
            return True
        return str(product.get("seller_id")) == str(current_user.get("_id"))

    def _present(self, product, current_user, compact=False):
        data = serialize_doc(product)
        data["view_count"] = int(product.get("view_count", 0) or 0)
        data["favorite_count"] = int(product.get("favorite_count", 0) or 0)
        code = normalize_category_code(product.get("category"))
        if not code and product.get("category_id"):
            category_doc = self.categories.find_by_id(product.get("category_id"))
            code = normalize_category_code((category_doc or {}).get("code"))
        if not code:
            code = "other"
        data["category"] = code
        data["category_name"] = product.get("category_name") or category_name(code)
        data["category_source"] = product.get("category_source") or "legacy"
        data["campus"] = normalize_campus(product.get("campus"), "")
        data["images"] = normalize_image_list(product.get("images") or [])
        data["cover_image"] = normalize_image_url(product.get("cover_image"))
        data["is_favorited"] = False
        if current_user and current_user.get("_id"):
            data["is_favorited"] = self.db.favorites.count_documents(
                {"user_id": ObjectId(str(current_user["_id"])), "product_id": product["_id"]}
            ) > 0
        seller = self.users.find_by_id(product["seller_id"])
        profile = self.users.find_profile(product["seller_id"])
        data["seller"] = {
            "id": str(seller["_id"]) if seller else str(product["seller_id"]),
            "nickname": (profile or {}).get("nickname", "未知用户"),
            "avatar": normalize_image_url((profile or {}).get("avatar") or (profile or {}).get("avatar_url", "")),
            "avatar_url": normalize_image_url((profile or {}).get("avatar_url") or (profile or {}).get("avatar", "")),
            "campus": normalize_campus((profile or {}).get("campus"), ""),
        }
        data["allowed_actions"] = self._allowed_actions(product, current_user)
        if not data.get("cover_image") and data.get("images"):
            data["cover_image"] = data["images"][0]
        if compact:
            return {
                key: data.get(key)
                for key in [
                    "id",
                    "title",
                    "price",
                    "cover_image",
                    "images",
                    "condition",
                    "category",
                    "category_name",
                    "category_source",
                    "category_id",
                    "stock",
                    "status",
                    "seller",
                    "campus",
                    "view_count",
                    "favorite_count",
                    "is_favorited",
                    "allowed_actions",
                    "recommendation_score",
                    "created_at",
                ]
            }
        return data

    def _allowed_actions(self, product, current_user):
        status = product["status"]
        roles = set((current_user or {}).get("roles", []))
        user_id = str((current_user or {}).get("_id", ""))
        is_owner = user_id and str(product.get("seller_id")) == user_id
        actions = {
            "can_edit": False,
            "can_submit_review": False,
            "can_off_shelf": False,
            "can_buy": False,
            "can_audit": False,
            "can_force_off_shelf": False,
            "can_delete": False,
            "can_republish": False,
        }
        if status == "on_sale" and not is_owner:
            actions["can_buy"] = True
        if is_owner and status in EDITABLE_STATUSES:
            actions["can_edit"] = True
        if is_owner and status in {"draft", "rejected"}:
            actions["can_submit_review"] = True
        if is_owner and status == "on_sale":
            actions["can_off_shelf"] = True
        if "admin" in roles and status == "pending_review":
            actions["can_audit"] = True
        if "admin" in roles and status == "on_sale":
            actions["can_force_off_shelf"] = True
        if is_owner and status in {"sold", "off_shelf"}:
            actions["can_delete"] = True
            actions["can_republish"] = True
        return actions

    def _record_product_view(self, user_id, product):
        user_object_id = ObjectId(str(user_id))
        product_id = product["_id"]
        self.db.product_views.update_one(
            {"user_id": user_object_id, "product_id": product_id},
            {
                "$set": {
                    "user_id": user_object_id,
                    "product_id": product_id,
                    "category_id": product.get("category_id"),
                    "viewed_at": utc_now(),
                },
                "$setOnInsert": {"created_at": utc_now()},
            },
            upsert=True,
        )


def _required_float(value, field, errors):
    try:
        amount = float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        errors.append({"field": field, "message": "价格必须是数字"})
        return None
    if amount <= 0:
        errors.append({"field": field, "message": "价格必须大于 0"})
        return None
    return round(amount, 2)


def _optional_float(value, field):
    if value in {None, ""}:
        return None
    try:
        amount = float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须是数字"}]) from exc
    if amount < 0:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额不能小于 0"}])
    return round(amount, 2)


def _optional_date(value, field, end=False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError("参数校验失败", [{"field": field, "message": "日期格式需为 YYYY-MM-DD"}]) from exc
    if parsed.tzinfo is None:
        parsed = datetime.combine(parsed.date(), time.max if end else time.min, tzinfo=timezone.utc)
    return parsed


class FavoriteService:
    def __init__(self, db):
        self.db = db
        self.products = ProductRepository(db)
        self.product_service = ProductService(db)

    def list_favorites(self, user_id, favorite_type="all"):
        user_object_id = ObjectId(str(user_id))
        rows = list(self.db.favorites.find({"user_id": user_object_id}).sort("created_at", -1))
        items = []
        stats = {"all": 0, "price_drop": 0, "valid": 0, "invalid": 0, "sold": 0}
        for row in rows:
            product = self.products.find_by_id(row["product_id"])
            if product:
                item = self.product_service._present(product, {"_id": user_object_id, "roles": []}, compact=True)
                favorited_price = row.get("favorited_price")
                current_price = float(product.get("price") or 0)
                item["favorited_price"] = favorited_price
                item["favorited_at"] = row.get("created_at").isoformat() if row.get("created_at") else None
                item["price_dropped"] = favorited_price is not None and current_price < float(favorited_price)
                item["favorite_invalid"] = product.get("status") == "off_shelf"
                item["favorite_valid"] = product.get("status") in {"on_sale", "locked", "sold"}
                item["favorite_note"] = _favorite_note(item)
                stats["all"] += 1
                if item["price_dropped"]:
                    stats["price_drop"] += 1
                if item["favorite_invalid"]:
                    stats["invalid"] += 1
                if item["favorite_valid"]:
                    stats["valid"] += 1
                if product.get("status") == "sold":
                    stats["sold"] += 1
                if favorite_type == "price_drop" and not item["price_dropped"]:
                    continue
                if favorite_type == "valid" and not item["favorite_valid"]:
                    continue
                if favorite_type == "invalid" and not item["favorite_invalid"]:
                    continue
                items.append(item)
        return {"items": items, "stats": stats, "type": favorite_type}

    def add_favorite(self, user_id, payload):
        product_id = to_object_id(payload.get("product_id"), "product_id")
        product = self.products.find_by_id(product_id)
        if not product or product.get("status") != "on_sale":
            raise NotFoundError("商品不存在或不可收藏")
        user_object_id = ObjectId(str(user_id))
        result = self.db.favorites.update_one(
            {"user_id": user_object_id, "product_id": product_id},
            {
                "$setOnInsert": {
                    "user_id": user_object_id,
                    "product_id": product_id,
                    "favorited_price": float(product.get("price") or 0),
                    "created_at": utc_now(),
                }
            },
            upsert=True,
        )
        if result.upserted_id:
            self.db.products.update_one({"_id": product_id}, {"$inc": {"favorite_count": 1}})
        return {"favorited": True, "product_id": str(product_id)}

    def delete_favorite(self, user_id, product_id):
        product_object_id = to_object_id(product_id, "product_id")
        result = self.db.favorites.delete_one({"user_id": ObjectId(str(user_id)), "product_id": product_object_id})
        if result.deleted_count:
            self.db.products.update_one({"_id": product_object_id, "favorite_count": {"$gt": 0}}, {"$inc": {"favorite_count": -1}})
        return {"favorited": False, "product_id": str(product_object_id)}

    def cleanup_invalid(self, user_id):
        user_object_id = ObjectId(str(user_id))
        rows = list(self.db.favorites.find({"user_id": user_object_id}))
        removed = 0
        for row in rows:
            product = self.products.find_by_id(row["product_id"])
            if product and product.get("status") == "off_shelf":
                result = self.db.favorites.delete_one({"_id": row["_id"]})
                removed += result.deleted_count
                if result.deleted_count:
                    self.db.products.update_one(
                        {"_id": product["_id"], "favorite_count": {"$gt": 0}},
                        {"$inc": {"favorite_count": -1}},
                    )
        return {"removed": removed}


def _favorite_note(item):
    if item.get("favorite_invalid"):
        return "卖家已下架，建议清理"
    if item.get("status") == "sold":
        return "已售出，可手动移除"
    if item.get("price_dropped"):
        return "收藏后降价"
    return "仍可查看"
