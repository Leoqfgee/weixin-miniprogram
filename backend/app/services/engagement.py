from datetime import datetime, time, timedelta, timezone
from time import perf_counter

from bson import ObjectId
from pymongo import DESCENDING

from ..adapters.ai import DashScopeTextClient
from ..repositories.escrows import EscrowRepository
from ..repositories.logs import BusinessLogRepository, OperationLogRepository
from ..repositories.orders import OrderRepository
from ..repositories.payments import PaymentRepository
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.images import normalize_image_url
from ..utils.serializers import serialize_doc, to_object_id


def utc_now():
    return datetime.now(timezone.utc)


REFUND_STATUS_META = {
    "requested": {"text": "待处理", "group": "pending"},
    "seller_agreed": {"text": "退款中", "group": "refunding"},
    "refunding": {"text": "退款中", "group": "refunding"},
    "refunded": {"text": "已退款", "group": "refunded"},
    "partial_refunded": {"text": "已退款", "group": "refunded"},
    "seller_rejected": {"text": "已拒绝", "group": "rejected"},
    "rejected": {"text": "已拒绝", "group": "rejected"},
    "closed": {"text": "已关闭", "group": "closed"},
}

REFUND_TYPE_TEXT = {
    "refund_only": "仅退款",
    "return_and_refund": "退货退款",
}

REFUND_STATUS_QUERY = {
    "pending": {"requested"},
    "requested": {"requested"},
    "refunding": {"seller_agreed", "refunding"},
    "refunded": {"refunded", "partial_refunded"},
    "rejected": {"seller_rejected", "rejected"},
    "closed": {"closed"},
}


class MessageService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.products = ProductRepository(db)

    def send_message(self, sender_id, payload):
        receiver_id = to_object_id(payload.get("receiver_id"), "receiver_id")
        product_id = payload.get("product_id")
        order_id = to_object_id(payload.get("order_id"), "order_id") if payload.get("order_id") else None
        message_type = (payload.get("message_type") or "text").strip()
        content = (payload.get("content") or "").strip()
        image_url = (payload.get("image_url") or "").strip()
        if message_type not in {"text", "image", "video", "voice", "product", "review", "system"}:
            raise ValidationError("参数校验失败", [{"field": "message_type", "message": "消息类型不合法"}])
        if message_type in {"image", "video", "voice"} and not image_url:
            raise ValidationError("参数校验失败", [{"field": "image_url", "message": "媒体消息不能为空"}])
        if message_type not in {"image", "video", "voice"} and not content:
            raise ValidationError("参数校验失败", [{"field": "content", "message": "消息内容不能为空"}])
        if str(receiver_id) == str(sender_id):
            raise ConflictError("不能给自己发送消息")
        if not self.users.find_by_id(receiver_id):
            raise NotFoundError("接收方不存在")

        product_object_id = to_object_id(product_id, "product_id") if product_id else None
        if order_id:
            order = self.db.orders.find_one({"_id": order_id})
            if not order:
                raise NotFoundError("订单不存在")
            participants = {str(order["buyer_id"]), str(order["seller_id"])}
            if str(sender_id) not in participants or str(receiver_id) not in participants:
                raise ForbiddenError("无权限使用该订单会话")
            product_object_id = order.get("product_id") or product_object_id
        user_pair = sorted([str(sender_id), str(receiver_id)])
        conversation_id = "_".join(user_pair + ([str(product_object_id)] if product_object_id else []))
        doc = {
            "conversation_id": conversation_id,
            "type": "private",
            "sender_id": ObjectId(str(sender_id)),
            "receiver_id": receiver_id,
            "product_id": product_object_id,
            "order_id": order_id,
            "message_type": message_type,
            "content": content,
            "image_url": image_url,
            "review_id": to_object_id(payload.get("review_id"), "review_id") if payload.get("review_id") else None,
            "read_at": None,
            "created_at": utc_now(),
        }
        result = self.db.messages.insert_one(doc)
        return serialize_doc(self.db.messages.find_one({"_id": result.inserted_id}))

    def get_support_contact(self, user_id):
        admin = self.db.users.find_one({"roles": "admin", "status": "active", "_id": {"$ne": ObjectId(str(user_id))}})
        if not admin:
            raise NotFoundError("暂未配置可用的管理员客服")
        profile = self.users.find_profile(admin["_id"]) or {}
        return {
            "id": str(admin["_id"]),
            "nickname": "平台客服",
            "avatar": profile.get("avatar") or profile.get("avatar_url", ""),
        }

    def list_conversations(self, user_id):
        user_object_id = ObjectId(str(user_id))
        pipeline = [
            {"$match": {"$or": [{"sender_id": user_object_id}, {"receiver_id": user_object_id}]}},
            {"$sort": {"created_at": -1}},
            {
                "$group": {
                    "_id": "$conversation_id",
                    "last_message": {"$first": "$$ROOT"},
                    "unread_count": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$eq": ["$receiver_id", user_object_id]},
                                        {"$eq": ["$read_at", None]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {"$sort": {"last_message.created_at": -1}},
        ]
        return {"items": [self._present_conversation(item, user_object_id) for item in self.db.messages.aggregate(pipeline)]}

    def list_messages(self, user_id, conversation_id):
        user_object_id = ObjectId(str(user_id))
        query = {
            "conversation_id": conversation_id,
            "$or": [{"sender_id": user_object_id}, {"receiver_id": user_object_id}],
        }
        self.db.messages.update_many(
            {"conversation_id": conversation_id, "receiver_id": user_object_id, "read_at": None},
            {"$set": {"read_at": utc_now()}},
        )
        items = list(self.db.messages.find(query).sort("created_at", 1))
        return {
            "items": [self._present_message(item, user_object_id) for item in items],
            "context": self._conversation_context(items[-1], user_object_id) if items else {},
        }

    def list_notifications(self, user_id):
        user_object_id = ObjectId(str(user_id))
        items = list(
            self.db.messages.find({"type": "system", "receiver_id": user_object_id})
            .sort("created_at", DESCENDING)
            .limit(50)
        )
        return {"items": [self._present_message(item, user_object_id) for item in items]}

    def _present_conversation(self, row, user_id):
        data = serialize_doc(row)
        last = row.get("last_message", {})
        other_id = last.get("receiver_id") if str(last.get("sender_id")) == str(user_id) else last.get("sender_id")
        other_user = self.users.find_by_id(other_id) if other_id else None
        other_profile = self.users.find_profile(other_id) if other_id else None
        product = self.products.find_by_id(last.get("product_id")) if last.get("product_id") else None
        order = self._conversation_order(last, user_id)
        product_snapshot = {}
        if order:
            order_item = self.db.order_items.find_one({"order_id": order["_id"]}) or {}
            product_snapshot = order_item.get("product_snapshot", {}) or {}
        data["conversation_id"] = data.get("id")
        data["other_user"] = {
            "id": str(other_id) if other_id else "",
            "nickname": "平台客服" if "admin" in other_user.get("roles", []) else (other_profile or {}).get("nickname", "校园用户"),
            "avatar": normalize_image_url((other_profile or {}).get("avatar") or (other_profile or {}).get("avatar_url", "")),
            "campus": (other_profile or {}).get("campus", ""),
        } if other_user else None
        data["order_id"] = str(order["_id"]) if order else ""
        data["product"] = self._conversation_product(product, product_snapshot)
        data["updated_at"] = data.get("last_message", {}).get("created_at")
        return data

    def _present_message(self, message, user_id):
        data = serialize_doc(message)
        sender = self.users.find_by_id(message.get("sender_id"))
        sender_profile = self.users.find_profile(message.get("sender_id")) or {}
        data["is_mine"] = str(message.get("sender_id")) == str(user_id)
        data["sender"] = {
            "id": str(message.get("sender_id")),
            "nickname": "平台客服" if sender and "admin" in sender.get("roles", []) else sender_profile.get("nickname", "校园用户"),
            "avatar": normalize_image_url(sender_profile.get("avatar") or sender_profile.get("avatar_url", "")),
        }
        return data

    def _conversation_context(self, message, user_id):
        if not message:
            return {}
        product = self.products.find_by_id(message.get("product_id")) if message.get("product_id") else None
        order = self._conversation_order(message, user_id)
        product_snapshot = {}
        if order:
            order_item = self.db.order_items.find_one({"order_id": order["_id"]}) or {}
            product_snapshot = order_item.get("product_snapshot", {}) or {}
        return {
            "order_id": str(order["_id"]) if order else "",
            "product": self._conversation_product(product, product_snapshot),
        }

    def _conversation_order(self, message, user_id):
        if not message:
            return None
        if message.get("order_id"):
            return self.db.orders.find_one({"_id": message["order_id"]})
        product_id = message.get("product_id")
        if not product_id:
            return None
        other_id = message.get("receiver_id") if str(message.get("sender_id")) == str(user_id) else message.get("sender_id")
        return self.db.orders.find_one(
            {
                "product_id": product_id,
                "$or": [
                    {"buyer_id": user_id, "seller_id": other_id},
                    {"buyer_id": other_id, "seller_id": user_id},
                ],
            },
            sort=[("created_at", DESCENDING)],
        )

    def _conversation_product(self, product, snapshot=None):
        snapshot = snapshot or {}
        if not product and not snapshot:
            return None
        return {
            "id": str((product or {}).get("_id") or snapshot.get("product_id") or ""),
            "title": (product or {}).get("title") or snapshot.get("title", ""),
            "cover_image": normalize_image_url((product or {}).get("cover_image") or snapshot.get("cover_image", "")),
            "price": (product or {}).get("price") or snapshot.get("price", 0),
            "condition": (product or {}).get("condition") or snapshot.get("condition", ""),
            "status": (product or {}).get("status", ""),
        }


class ReviewService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.products = ProductRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_review(self, reviewer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        is_buyer = str(order["buyer_id"]) == str(reviewer_id)
        is_seller = str(order["seller_id"]) == str(reviewer_id)
        if not is_buyer and not is_seller:
            raise ForbiddenError("只有交易双方可以评价订单")
        if order["status"] not in {"pending_review", "completed"}:
            raise ConflictError("确认收货后才可以评价")
        rating = payload.get("rating")
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValidationError("参数校验失败", [{"field": "rating", "message": "评分必须为 1-5"}])
        content = (payload.get("content") or "").strip()
        reviewer_object_id = ObjectId(str(reviewer_id))
        reviewee_id = order["seller_id"] if is_buyer else order["buyer_id"]
        reviewer_role = "buyer" if is_buyer else "seller"
        doc = {
            "order_id": order_id,
            "reviewer_id": reviewer_object_id,
            "reviewee_id": reviewee_id,
            "reviewer_role": reviewer_role,
            "anonymous": bool(payload.get("anonymous")),
            "rating": rating,
            "content": content,
            "updated_at": utc_now(),
            "created_at": utc_now(),
        }
        self.db.reviews.update_one(
            {"order_id": order_id, "reviewer_id": reviewer_object_id},
            {"$set": doc},
            upsert=True,
        )
        review = self.db.reviews.find_one({"order_id": order_id, "reviewer_id": reviewer_object_id})
        to_status = order["status"]
        if is_buyer and order["status"] == "pending_review":
            updated_order = self.orders.update_fields(order_id, {"status": "completed", "completed_at": utc_now()})
            to_status = updated_order["status"]
            for item in self.db.order_items.find({"order_id": order_id}):
                self.products.mark_sold(item["product_id"])
                self.logs.create("product_sold", "product", item["product_id"], reviewer_object_id, "buyer", "locked", "sold")
        self.logs.create("create_review", "order", order_id, reviewer_object_id, reviewer_role, order["status"], to_status)
        self._append_review_message(order, review, reviewee_id)
        return self._present_review(review)

    def get_review(self, review_id):
        review = self.db.reviews.find_one({"_id": to_object_id(review_id, "review_id")})
        if not review:
            raise NotFoundError("评价不存在")
        return self._present_review(review)

    def list_user_reviews(self, user_id):
        items = list(
            self.db.reviews.find({"reviewee_id": to_object_id(user_id, "user_id")})
            .sort("created_at", DESCENDING)
            .limit(50)
        )
        good_count = sum(1 for item in items if item.get("rating", 0) >= 4)
        return {
            "items": [self._present_review(item) for item in items],
            "total": len(items),
            "good_rate": round(good_count * 100 / len(items), 1) if items else 100.0,
        }

    def _append_review_message(self, order, review, receiver_id):
        user_pair = sorted([str(review["reviewer_id"]), str(receiver_id)])
        conversation_id = "_".join(user_pair + [str(order["product_id"])])
        self.db.messages.insert_one(
            {
                "conversation_id": conversation_id,
                "type": "private",
                "sender_id": review["reviewer_id"],
                "receiver_id": receiver_id,
                "product_id": order["product_id"],
                "order_id": order["_id"],
                "message_type": "review",
                "content": "对方完成了评价，点击查看详情",
                "review_id": review["_id"],
                "image_url": "",
                "read_at": None,
                "created_at": utc_now(),
            }
        )

    def _present_review(self, review):
        data = serialize_doc(review)
        profile = self.db.user_profiles.find_one({"user_id": review["reviewer_id"]}) or {}
        data["reviewer"] = {
            "id": "" if review.get("anonymous") else str(review["reviewer_id"]),
            "nickname": "匿名用户" if review.get("anonymous") else profile.get("nickname", "校园用户"),
            "avatar": "" if review.get("anonymous") else profile.get("avatar") or profile.get("avatar_url", ""),
        }
        return data


class RefundService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.escrows = EscrowRepository(db)
        self.products = ProductRepository(db)
        self.users = UserRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_refund(self, buyer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(buyer_id):
            raise ForbiddenError("只有买家可以申请售后")
        if order["status"] not in {"pending_delivery", "pending_receive"}:
            raise ConflictError("当前订单状态不允许申请售后")
        amount = _amount(payload.get("amount"), "amount")
        if amount > float(order["pay_amount"]):
            raise ValidationError("参数校验失败", [{"field": "amount", "message": "退款金额不能超过实付金额"}])
        reason = (payload.get("reason") or "").strip()
        if not reason:
            raise ValidationError("参数校验失败", [{"field": "reason", "message": "退款原因不能为空"}])
        existing = self.db.refunds.find_one({"order_id": order_id, "status": {"$nin": ["refunded", "closed"]}})
        if existing:
            return self._present_refund(existing, ObjectId(str(buyer_id)))
        self.orders.update_fields(order_id, {"status": "refunding", "pre_refund_status": order["status"]})
        doc = {
            "order_id": order_id,
            "product_id": order.get("product_id"),
            "buyer_id": ObjectId(str(buyer_id)),
            "seller_id": order["seller_id"],
            "applicant_id": ObjectId(str(buyer_id)),
            "refund_type": payload.get("refund_type") or "refund_only",
            "amount": amount,
            "request_amount": amount,
            "final_refund_amount": None,
            "reason": reason,
            "description": (payload.get("description") or "").strip(),
            "evidence_images": payload.get("evidence_images") or [],
            "status": "requested",
            "seller_result": "",
            "seller_reason": "",
            "seller_response": "",
            "seller_handled_at": None,
            "admin_result": "",
            "admin_decision": "",
            "admin_reason": "",
            "admin_handled_at": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.refunds.insert_one(doc)
        self.logs.create("apply_refund", "order", order_id, ObjectId(str(buyer_id)), "buyer", order["status"], "refunding", reason)
        refund = self.db.refunds.find_one({"_id": result.inserted_id})
        self._append_refund_system_message(order, refund, order["seller_id"], "买家提交了售后申请，请及时处理", "refund_requested")
        return self._present_refund(refund, ObjectId(str(buyer_id)))

    def list_refunds(self, user, args):
        status = args.get("status")
        role = (args.get("role") or "").strip()
        order_id = args.get("order_id")
        page = max(int(args.get("page", 1) or 1), 1)
        page_size = min(max(int(args.get("page_size") or args.get("pageSize") or 20), 1), 50)
        query = {}
        if status:
            statuses = REFUND_STATUS_QUERY.get(status, {status})
            query["status"] = {"$in": list(statuses)}
        if order_id:
            query["order_id"] = to_object_id(order_id, "order_id")
        if "admin" not in user.get("roles", []):
            if role == "seller":
                query["seller_id"] = user["_id"]
            elif role == "buyer":
                query["buyer_id"] = user["_id"]
            else:
                query["$or"] = [{"buyer_id": user["_id"]}, {"seller_id": user["_id"]}]
        total = self.db.refunds.count_documents(query)
        items = list(
            self.db.refunds.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        self._mark_refund_messages_read([item["_id"] for item in items], user["_id"])
        return {
            "items": [self._present_refund(item, user["_id"], user) for item in items],
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }

    def get_refund(self, refund_id, user):
        refund = self._get_refund(refund_id)
        if "admin" not in user.get("roles", []) and str(user["_id"]) not in {str(refund["buyer_id"]), str(refund["seller_id"])}:
            raise ForbiddenError("无权限查看该退款")
        self._mark_refund_messages_read([refund["_id"]], user["_id"])
        return self._present_refund(refund, user["_id"], user)

    def seller_agree(self, refund_id, seller_id, payload=None):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理售后")
        if refund["status"] != "requested":
            raise ConflictError("当前退款状态不允许卖家处理")
        self._mark_refund_messages_read([refund["_id"]], ObjectId(str(seller_id)))
        order = self.orders.find_by_id(refund["order_id"])
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "seller_agreed",
                    "seller_result": "agreed",
                    "seller_reason": ((payload or {}).get("reason") or "").strip(),
                    "seller_response": ((payload or {}).get("reason") or "").strip(),
                    "final_refund_amount": refund.get("amount"),
                    "seller_handled_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        updated_refund = self._get_refund(refund["_id"])
        self._execute_refund(order, updated_refund, ObjectId(str(seller_id)), "seller", "seller_agree_refund")
        self._append_refund_system_message(order, updated_refund, order["buyer_id"], "卖家已同意售后申请，退款已处理", "refund_seller_agreed")
        return self._present_refund(self._get_refund(refund["_id"]), ObjectId(str(seller_id)))

    def seller_reject(self, refund_id, seller_id, payload=None):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理售后")
        if refund["status"] != "requested":
            raise ConflictError("当前退款状态不允许卖家处理")
        reason = ((payload or {}).get("reason") or "").strip()
        if not reason:
            raise ValidationError("参数校验失败", [{"field": "reason", "message": "请填写拒绝原因"}])
        self._mark_refund_messages_read([refund["_id"]], ObjectId(str(seller_id)))
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "seller_rejected",
                    "seller_result": "rejected",
                    "seller_reason": reason,
                    "seller_response": reason,
                    "seller_handled_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        self.logs.create("seller_reject_refund", "refund", refund["_id"], ObjectId(str(seller_id)), "seller", "requested", "seller_rejected", reason)
        self._append_refund_system_message(self.orders.find_by_id(refund["order_id"]), refund, refund["buyer_id"], f"卖家拒绝了退款申请：{reason}", "refund_seller_rejected")
        return self._present_refund(self._get_refund(refund["_id"]), ObjectId(str(seller_id)))

    def seller_handle(self, refund_id, seller_id, payload):
        result = payload.get("action") or payload.get("result")
        if result in {"agree", "approved"}:
            return self.seller_agree(refund_id, seller_id, payload)
        if result in {"refuse", "reject", "rejected"}:
            return self.seller_reject(refund_id, seller_id, payload)
        if result == "partial_refund":
            return self.seller_partial_refund(refund_id, seller_id, payload)
        raise ValidationError("参数校验失败", [{"field": "result", "message": "处理结果不合法"}])

    def seller_partial_refund(self, refund_id, seller_id, payload):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理售后")
        if refund["status"] != "requested":
            raise ConflictError("当前售后状态不允许卖家处理")
        order = self.orders.find_by_id(refund["order_id"])
        final_amount = _amount(payload.get("final_refund_amount") or payload.get("amount"), "final_refund_amount")
        if final_amount > float(refund.get("amount") or order.get("pay_amount")):
            raise ValidationError("参数校验失败", [{"field": "final_refund_amount", "message": "部分退款金额不能超过申请金额"}])
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "partial_refunded",
                    "seller_result": "partial_refund",
                    "seller_reason": (payload.get("reason") or "").strip(),
                    "seller_response": (payload.get("reason") or "").strip(),
                    "final_refund_amount": final_amount,
                    "seller_handled_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        updated_refund = self._get_refund(refund["_id"])
        self._execute_refund(order, updated_refund, ObjectId(str(seller_id)), "seller", "seller_partial_refund")
        self.db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": "partial_refunded", "updated_at": utc_now()}})
        self._append_refund_system_message(order, updated_refund, order["buyer_id"], f"卖家提出部分退款 ¥{final_amount}，售后已处理", "refund_partial")
        return self._present_refund(self._get_refund(refund["_id"]), ObjectId(str(seller_id)))

    def admin_arbitrate(self, refund_id, admin_user, payload, trace_id=None):
        refund = self._get_refund(refund_id)
        order = self.orders.find_by_id(refund["order_id"])
        result = payload.get("result")
        if result not in {"approved", "rejected", "partial_refund"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "仲裁结果不合法"}])
        if result == "approved":
            self._execute_refund(order, refund, admin_user["_id"], "admin", "admin_arbitrate")
            self._append_refund_system_message(order, self._get_refund(refund["_id"]), order["buyer_id"], "平台支持买家售后申请，退款已处理", "refund_admin_approved")
            return self._present_refund(self._get_refund(refund["_id"]), admin_user["_id"], admin_user)
        if result == "partial_refund":
            final_amount = _amount(payload.get("final_refund_amount") or payload.get("amount"), "final_refund_amount")
            self.db.refunds.update_one(
                {"_id": refund["_id"]},
                {"$set": {"status": "partial_refunded", "admin_result": "partial_refund", "admin_decision": "partial_refund", "admin_reason": (payload.get("reason") or "").strip(), "final_refund_amount": final_amount, "admin_handled_at": utc_now(), "updated_at": utc_now()}},
            )
            self._execute_refund(order, self._get_refund(refund["_id"]), admin_user["_id"], "admin", "admin_partial_refund")
            self.db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": "partial_refunded", "updated_at": utc_now()}})
            self._append_refund_system_message(order, self._get_refund(refund["_id"]), order["buyer_id"], f"平台裁定部分退款 ¥{final_amount}，售后已处理", "refund_admin_partial")
            return self._present_refund(self._get_refund(refund["_id"]), admin_user["_id"], admin_user)
        restore_status = order.get("pre_refund_status") or "pending_delivery"
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {"$set": {"status": "rejected", "admin_result": "rejected", "admin_decision": "rejected", "admin_reason": (payload.get("reason") or "").strip(), "admin_handled_at": utc_now(), "updated_at": utc_now()}},
        )
        self.orders.update_fields(order["_id"], {"status": restore_status, "pre_refund_status": ""})
        self.logs.create("admin_arbitrate", "refund", refund["_id"], admin_user["_id"], "admin", refund["status"], "rejected", payload.get("reason") or "", {"result": result})
        self._append_refund_system_message(order, refund, order["buyer_id"], "平台支持卖家拒绝售后，订单恢复原状态", "refund_admin_rejected")
        return self._present_refund(self._get_refund(refund["_id"]), admin_user["_id"], admin_user)

    def _execute_refund(self, order, refund, operator_id, operator_role, action):
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") != "refunded":
            self.payments.update_fields(payment["_id"], {"status": "refunded", "refunded_at": utc_now()})
        escrow = self.escrows.find_by_order(order["_id"])
        if escrow and escrow.get("status") != "refunded":
            self.escrows.update_status(order["_id"], "refunded")
        self.orders.update_fields(order["_id"], {"status": "refunded", "pre_refund_status": ""})
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {"$set": {"status": "refunded", "final_refund_amount": refund.get("final_refund_amount") or refund.get("amount") or order.get("pay_amount"), "updated_at": utc_now()}},
        )
        for item in self.db.order_items.find({"order_id": order["_id"]}):
            self.products.mark_off_shelf_after_refund(item["product_id"])
            self.logs.create("product_off_shelf_after_refund", "product", item["product_id"], operator_id, operator_role, "locked", "off_shelf")
        self.logs.create(action, "refund", refund["_id"], operator_id, operator_role, refund["status"], "refunded")
        self.logs.create("refund_success", "order", order["_id"], operator_id, operator_role, order["status"], "refunded")

    def _get_refund(self, refund_id):
        refund = self.db.refunds.find_one({"_id": to_object_id(refund_id, "refund_id")})
        if not refund:
            raise NotFoundError("退款申请不存在")
        return refund


    def _present_refund(self, refund, current_user_id=None, current_user=None):
        data = serialize_doc(refund)
        order = self.orders.find_by_id(refund["order_id"])
        items = list(self.db.order_items.find({"order_id": refund["order_id"]}))
        first_item = items[0] if items else {}
        product_snapshot = first_item.get("product_snapshot", {})
        product = self.products.find_by_id(refund.get("product_id")) if refund.get("product_id") else None
        status_meta = REFUND_STATUS_META.get(refund.get("status"), {"text": refund.get("status", ""), "group": refund.get("status", "")})
        data["refund_no"] = self._readable_refund_no(refund)
        data["after_sale_no"] = data["refund_no"]
        data["status_text"] = status_meta["text"]
        data["status_group"] = status_meta["group"]
        data["refund_type_text"] = REFUND_TYPE_TEXT.get(refund.get("refund_type"), refund.get("refund_type", ""))
        data["order"] = {
            "id": str((order or {}).get("_id") or ""),
            "order_no": (order or {}).get("order_no", ""),
            "status": (order or {}).get("status", ""),
            "pay_amount": (order or {}).get("pay_amount", 0),
            "total_amount": (order or {}).get("total_amount", 0),
        }
        data["order_no"] = (order or {}).get("order_no", "")
        condition = (product or {}).get("condition") or product_snapshot.get("condition") or ""
        spec = product_snapshot.get("spec") or product_snapshot.get("sku_text") or condition
        data["product"] = {
            "id": str((product or {}).get("_id") or product_snapshot.get("product_id") or ""),
            "title": (product or {}).get("title") or product_snapshot.get("title", ""),
            "cover_image": normalize_image_url((product or {}).get("cover_image") or product_snapshot.get("cover_image", "")),
            "price": (product or {}).get("price") or product_snapshot.get("price", 0),
            "quantity": first_item.get("quantity", 1),
            "condition": condition,
            "condition_text": condition,
            "spec": spec,
            "spec_text": spec,
            "status": (product or {}).get("status") or "",
        }
        data["buyer"] = self._party(refund["buyer_id"])
        data["seller"] = self._party(refund["seller_id"])
        data["request_amount"] = refund.get("request_amount", refund.get("amount"))
        data["final_refund_amount"] = refund.get("final_refund_amount")
        data["display_amount"] = refund.get("final_refund_amount") or refund.get("request_amount") or refund.get("amount")
        data["reason_text"] = refund.get("reason", "")
        data["seller_response"] = refund.get("seller_response") or refund.get("seller_reason", "")
        data["admin_decision"] = refund.get("admin_decision") or refund.get("admin_result", "")
        data["delivery"] = self._refund_delivery(refund["order_id"])
        data["timeline"] = self._refund_timeline(refund)
        user_id = str(current_user_id or "")
        is_admin = current_user and "admin" in current_user.get("roles", [])
        is_buyer = user_id == str(refund["buyer_id"])
        contact_party = data["seller"] if is_buyer else data["buyer"]
        data["current_role"] = "buyer" if is_buyer else "seller"
        data["conversation_id"] = _order_conversation_id(order) if order else ""
        data["contact_user"] = contact_party
        data["contact_label"] = "联系卖家" if is_buyer else "联系买家"
        data["counterparty"] = contact_party
        data["counterparty_label"] = "卖家" if is_buyer else "买家"
        data["permissions"] = {
            "can_seller_handle": user_id == str(refund["seller_id"]) and refund.get("status") == "requested",
            "can_apply_appeal": user_id == str(refund["buyer_id"]) and refund.get("status") == "seller_rejected",
            "can_admin_arbitrate": bool(is_admin) and refund.get("status") in {"requested", "seller_rejected"},
            "can_contact": bool(contact_party.get("id")),
        }
        return data

    def _party(self, user_id):
        profile = self.users.find_profile(user_id) or {}
        user = self.users.find_by_id(user_id) or {}
        phone = user.get("phone") or profile.get("contact_phone") or ""
        return {
            "id": str(user_id),
            "nickname": profile.get("nickname", "校园同学"),
            "avatar": normalize_image_url(profile.get("avatar") or profile.get("avatar_url", "")),
            "campus": profile.get("campus", ""),
            "phone": phone,
            "phone_masked": self._mask_phone(phone),
        }

    def _readable_refund_no(self, refund):
        created = refund.get("created_at") or utc_now()
        if hasattr(created, "strftime"):
            day = created.strftime("%Y%m%d")
        else:
            day = str(created)[:10].replace("-", "") or utc_now().strftime("%Y%m%d")
        return f"SH{day}{str(refund['_id'])[-4:].upper()}"

    def _mask_phone(self, phone):
        value = str(phone or "")
        if len(value) < 7:
            return value
        return f"{value[:3]}****{value[-4:]}"

    def _refund_delivery(self, order_id):
        delivery = self.db.deliveries.find_one({"order_id": order_id}, sort=[("created_at", DESCENDING)])
        if not delivery:
            return {}
        data = serialize_doc(delivery)
        return {
            "delivery_type": data.get("delivery_type", ""),
            "express_company": data.get("express_company") or data.get("company") or "",
            "tracking_no": data.get("tracking_no") or data.get("tracking_number") or "",
            "meet_location": data.get("meet_location", ""),
        }

    def _mark_refund_messages_read(self, refund_ids, user_id):
        ids = [item if isinstance(item, ObjectId) else ObjectId(str(item)) for item in refund_ids if item]
        if not ids or not user_id:
            return
        self.db.messages.update_many(
            {
                "refund_id": {"$in": ids},
                "receiver_id": user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id)),
                "read_at": None,
            },
            {"$set": {"read_at": utc_now()}},
        )

    def _refund_timeline(self, refund):
        items = [{"label": "提交售后申请", "time": refund.get("created_at"), "status": "done"}]
        if refund.get("seller_handled_at"):
            label = "卖家同意售后" if refund.get("seller_result") == "agreed" else "卖家处理售后"
            items.append({"label": label, "time": refund.get("seller_handled_at"), "status": "done"})
        if refund.get("admin_handled_at"):
            items.append({"label": "平台仲裁完成", "time": refund.get("admin_handled_at"), "status": "done"})
        if refund.get("status") in {"refunded", "partial_refunded"}:
            items.append({"label": "退款处理完成", "time": refund.get("updated_at"), "status": "done"})
        return [serialize_doc(item) for item in items]

    def _append_refund_system_message(self, order, refund, receiver_id, content, action):
        if not order or not receiver_id:
            return
        user_pair = sorted([str(order["buyer_id"]), str(order["seller_id"])])
        conversation_id = "_".join(user_pair + [str(order["product_id"])])
        sender_id = order["buyer_id"] if str(receiver_id) == str(order["seller_id"]) else order["seller_id"]
        self.db.messages.insert_one(
            {
                "conversation_id": conversation_id,
                "type": "private",
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "product_id": order["product_id"],
                "message_type": "system",
                "content": content,
                "system_action": action,
                "order_id": order["_id"],
                "refund_id": refund["_id"],
                "image_url": "",
                "read_at": None,
                "created_at": utc_now(),
            }
        )


class AppealService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.escrows = EscrowRepository(db)
        self.products = ProductRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_appeal(self, user_id, payload):
        refund = self.db.refunds.find_one({"_id": to_object_id(payload.get("refund_id"), "refund_id")})
        if not refund:
            raise NotFoundError("退款申请不存在")
        if str(refund["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以申请平台介入")
        if refund["status"] != "seller_rejected":
            raise ConflictError("只有卖家拒绝退款后才能申请平台介入")
        existing = self.db.appeals.find_one({"refund_id": refund["_id"], "status": "pending"})
        if existing:
            return serialize_doc(existing)
        order = self.orders.find_by_id(refund["order_id"])
        doc = {
            "order_id": order["_id"],
            "refund_id": refund["_id"],
            "buyer_id": refund["buyer_id"],
            "seller_id": refund["seller_id"],
            "applicant_id": ObjectId(str(user_id)),
            "reason": (payload.get("reason") or "").strip(),
            "description": (payload.get("description") or "").strip(),
            "evidence_images": payload.get("evidence_images") or [],
            "chat_snapshot_ids": [],
            "delivery_snapshot": serialize_doc(self.db.deliveries.find_one({"order_id": order["_id"]})) or {},
            "payment_snapshot": serialize_doc(self.payments.find_by_order(order["_id"])) or {},
            "product_snapshot": (self.db.order_items.find_one({"order_id": order["_id"]}) or {}).get("product_snapshot", {}),
            "status": "pending",
            "admin_id": None,
            "admin_result": "",
            "admin_reason": "",
            "force_action": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "handled_at": None,
        }
        result = self.db.appeals.insert_one(doc)
        self.logs.create("apply_appeal", "appeal", result.inserted_id, ObjectId(str(user_id)), "buyer", None, "pending")
        return serialize_doc(self.db.appeals.find_one({"_id": result.inserted_id}))

    def get_appeal(self, appeal_id, user):
        appeal = self._get_appeal(appeal_id)
        if "admin" not in user.get("roles", []) and str(user["_id"]) not in {str(appeal["buyer_id"]), str(appeal["seller_id"])}:
            raise ForbiddenError("无权限查看该申诉")
        return self._present_appeal(appeal)

    def list_appeals(self, admin_user, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        query = {}
        if args.get("status"):
            query["status"] = args.get("status")
        total = self.db.appeals.count_documents(query)
        items = list(
            self.db.appeals.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return {
            "items": [self._present_appeal(item) for item in items],
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }

    def arbitrate(self, appeal_id, admin_user, payload):
        appeal = self._get_appeal(appeal_id)
        if appeal["status"] != "pending":
            raise ConflictError("当前申诉状态不允许仲裁")
        force_action = payload.get("force_action") or payload.get("result")
        if force_action not in {"refund", "reject_refund", "partial_refund"}:
            raise ValidationError("参数校验失败", [{"field": "force_action", "message": "仲裁动作不合法"}])
        refund = self.db.refunds.find_one({"_id": appeal["refund_id"]})
        order = self.orders.find_by_id(appeal["order_id"])
        if force_action in {"refund", "partial_refund"}:
            status = "approved" if force_action == "refund" else "partial_refund"
            self._refund_by_admin(order, refund, admin_user["_id"])
            appeal_status = status
        elif force_action == "reject_refund":
            restore_status = order.get("pre_refund_status") or "pending_delivery"
            self.db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": "closed", "admin_result": "rejected", "admin_reason": payload.get("reason") or "", "updated_at": utc_now()}})
            self.orders.update_fields(order["_id"], {"status": restore_status, "pre_refund_status": ""})
            appeal_status = "rejected"
        self.db.appeals.update_one(
            {"_id": appeal["_id"]},
            {"$set": {"status": appeal_status, "admin_id": admin_user["_id"], "admin_result": force_action, "admin_reason": payload.get("reason") or "", "force_action": force_action, "handled_at": utc_now(), "updated_at": utc_now()}},
        )
        self.logs.create("admin_arbitrate", "appeal", appeal["_id"], admin_user["_id"], "admin", "pending", appeal_status, payload.get("reason") or "", {"force_action": force_action})
        return serialize_doc(self._get_appeal(appeal["_id"]))

    def _refund_by_admin(self, order, refund, admin_id):
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") != "refunded":
            self.payments.update_fields(payment["_id"], {"status": "refunded", "refunded_at": utc_now()})
        escrow = self.escrows.find_by_order(order["_id"])
        if escrow and escrow.get("status") != "refunded":
            self.escrows.update_status(order["_id"], "refunded")
        self.orders.update_fields(order["_id"], {"status": "refunded", "pre_refund_status": ""})
        self.db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": "refunded", "admin_result": "approved", "admin_handled_at": utc_now(), "updated_at": utc_now()}})
        for item in self.db.order_items.find({"order_id": order["_id"]}):
            self.products.mark_off_shelf_after_refund(item["product_id"])
        self.logs.create("refund_success", "order", order["_id"], admin_id, "admin", order["status"], "refunded")

    def _get_appeal(self, appeal_id):
        appeal = self.db.appeals.find_one({"_id": to_object_id(appeal_id, "appeal_id")})
        if not appeal:
            raise NotFoundError("平台介入申请不存在")
        return appeal

    def _present_appeal(self, appeal):
        data = serialize_doc(appeal)
        order = self.orders.find_by_id(appeal["order_id"])
        refund = self.db.refunds.find_one({"_id": appeal["refund_id"]})
        data["order"] = serialize_doc(order) if order else None
        data["refund"] = serialize_doc(refund) if refund else None
        if data["refund"]:
            status_meta = REFUND_STATUS_META.get(refund.get("status"), {"text": refund.get("status", ""), "group": refund.get("status", "")})
            data["refund"]["status_text"] = status_meta["text"]
            data["refund"]["status_group"] = status_meta["group"]
        data["payment"] = serialize_doc(self.payments.find_by_order(appeal["order_id"])) or {}
        data["escrow"] = serialize_doc(self.escrows.find_by_order(appeal["order_id"])) or {}
        data["delivery"] = serialize_doc(self.db.deliveries.find_one({"order_id": appeal["order_id"]})) or {}
        data["order_items"] = [serialize_doc(item) for item in self.db.order_items.find({"order_id": appeal["order_id"]})]
        if data["order_items"] and not data.get("product_snapshot"):
            data["product_snapshot"] = data["order_items"][0].get("product_snapshot", {})
        return data


class AiService:
    def __init__(self, db, config=None):
        self.db = db
        self.config = config or {}

    def product_copy(self, user_id, payload):
        action = (payload.get("action") or "both").strip()
        return self.generate(user_id, payload, action)

    def generate(self, user_id, payload, feature_type):
        action_map = {
            "title": "title",
            "polish": "description",
            "description": "description",
            "both": "both",
        }
        action = action_map.get(feature_type)
        if not action:
            raise ValidationError("参数校验失败", [{"field": "feature_type", "message": "AI 功能类型不合法"}])

        mode = self.config.get("AI_MODE", "qwen")
        model = self.config.get("QWEN_MODEL") or "qwen-plus"
        started = perf_counter()
        result_data = None
        error_message = ""
        success = False
        try:
            if mode == "mock":
                result_data = self._mock_product_copy(payload, action)
                success = True
                return self._store_log(user_id, feature_type, "mock", payload, result_data, success, error_message, started)
            if mode not in {"qwen", "dashscope"}:
                raise AppError(50302, "AI_MODE 必须配置为 qwen 或 dashscope 才能调用正式模型", 503)
            api_key = self.config.get("DASHSCOPE_API_KEY", "")
            if not api_key:
                raise AppError(50301, "AI 服务未配置 DASHSCOPE_API_KEY", 503)
            client = DashScopeTextClient(
                api_key=api_key,
                base_url=self.config.get("AI_BASE_URL"),
                model=model,
                timeout_seconds=self.config.get("AI_TIMEOUT_SECONDS", 30),
            )
            result_data = client.generate_product_copy(payload, action)
            success = True
            return self._store_log(user_id, feature_type, model, payload, result_data, success, error_message, started)
        except Exception as exc:
            error_message = getattr(exc, "message", str(exc))
            self._store_log(user_id, feature_type, model, payload, result_data or {}, success, error_message, started)
            raise

    def _mock_product_copy(self, payload, action):
        keyword = (payload.get("keywords") or payload.get("title") or payload.get("description") or "校园好物").strip()
        title_suggestions = [
            f"{keyword}，校内自提更方便",
            f"低价转让{keyword}",
            f"{keyword}实拍，可当面验货",
        ]
        description = (
            f"这件{keyword}适合校内同学日常使用，支持当面查看成色。"
            "如需更多细节可以直接联系卖家沟通，交易建议走平台订单。"
        )
        result = {"tags": ["校内交易", "可验货"]}
        if action in {"title", "both"}:
            result["title_suggestions"] = title_suggestions
        if action in {"description", "both"}:
            result["description"] = description
        return result

    def _store_log(self, user_id, feature_type, model, payload, result_data, success, error_message, started):
        latency_ms = int((perf_counter() - started) * 1000)
        doc = {
            "user_id": ObjectId(str(user_id)),
            "feature_type": feature_type,
            "model": model,
            "input_summary": _summary_text(payload),
            "output_summary": _summary_text(result_data),
            "success": bool(success),
            "error_message": error_message or "",
            "latency_ms": latency_ms,
            "payload": payload,
            "result": result_data,
            "created_at": utc_now(),
        }
        result = self.db.ai_generation_logs.insert_one(doc)
        if success:
            return {"ai_draft_id": str(result.inserted_id), **result_data}
        return {"ai_draft_id": str(result.inserted_id), "success": False}


class AdminReportService:
    def __init__(self, db):
        self.db = db

    def list_operation_logs(self, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        total = self.db.operation_logs.count_documents({})
        items = list(
            self.db.operation_logs.find({})
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return {"items": [serialize_doc(item) for item in items], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def stats(self):
        return {
            "users": self.db.users.count_documents({}),
            "products_on_sale": self.db.products.count_documents({"status": "on_sale"}),
            "products_pending_review": self.db.products.count_documents({"status": "pending_review"}),
            "orders": self.db.orders.count_documents({}),
            "orders_completed": self.db.orders.count_documents({"status": "completed"}),
            "refunds_pending": self.db.refunds.count_documents({"status": {"$in": ["requested", "seller_rejected"]}}),
        }

    def summary(self, args):
        query = _date_query(args)
        return {
            "products_published": self.db.products.count_documents(query),
            "orders_completed": self.db.orders.count_documents({"status": "completed", **query}),
            "users_new": self.db.users.count_documents(query),
            "active_users": self._active_user_count(query),
            "refunds": self.db.refunds.count_documents(query),
        }

    def products(self, args):
        return {"items": _group_by_date(self.db.products, _date_query(args))}

    def orders(self, args):
        return {"items": _group_by_date(self.db.orders, {"status": "completed", **_date_query(args)}, sum_field="pay_amount")}

    def categories(self, args):
        pipeline = [
            {"$match": _date_query(args)},
            {"$group": {"_id": "$category_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        rows = []
        for row in self.db.products.aggregate(pipeline):
            category = self.db.categories.find_one({"_id": row["_id"]})
            rows.append({"category_id": str(row["_id"]), "name": (category or {}).get("name", "未分类"), "count": row["count"]})
        return {"items": rows}

    def users(self, args):
        query = _date_query(args)
        return {
            "items": [
                {"label": "新增用户", "count": self.db.users.count_documents(query)},
                {"label": "发布商品用户", "count": len(self.db.products.distinct("seller_id", query))},
                {"label": "下单用户", "count": len(self.db.orders.distinct("buyer_id", query))},
                {"label": "发消息用户", "count": len(self.db.messages.distinct("sender_id", query))},
            ]
        }

    def _active_user_count(self, query):
        user_ids = set()
        for collection, field in [(self.db.products, "seller_id"), (self.db.orders, "buyer_id"), (self.db.messages, "sender_id")]:
            user_ids.update(str(item) for item in collection.distinct(field, query))
        return len(user_ids)


def _amount(value, field):
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须是数字"}]) from exc
    if amount <= 0:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须大于 0"}])
    return amount


def _order_conversation_id(order):
    if not order:
        return ""
    user_pair = sorted([str(order["buyer_id"]), str(order["seller_id"])])
    return "_".join(user_pair + [str(order["product_id"])])


def _summary_text(value, limit=240):
    text = str(serialize_doc(value) if isinstance(value, dict) else value)
    text = " ".join(text.split())
    return text[:limit]


def _date_query(args):
    start = args.get("start_date")
    end = args.get("end_date")
    if not start and not end:
        range_name = args.get("range") or "month"
        days = {"day": 1, "week": 7, "month": 30}.get(range_name, 30)
        start_dt = datetime.now(timezone.utc) - timedelta(days=days)
        return {"created_at": {"$gte": start_dt}}
    date_query = {}
    if start:
        date_query["$gte"] = datetime.combine(datetime.fromisoformat(start).date(), time.min, tzinfo=timezone.utc)
    if end:
        date_query["$lte"] = datetime.combine(datetime.fromisoformat(end).date(), time.max, tzinfo=timezone.utc)
    return {"created_at": date_query}


def _group_by_date(collection, query, sum_field=None):
    group = {"count": {"$sum": 1}}
    if sum_field:
        group["amount"] = {"$sum": f"${sum_field}"}
    pipeline = [
        {"$match": query},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, **group}},
        {"$sort": {"_id": 1}},
    ]
    return [{"date": row["_id"], "count": row.get("count", 0), "amount": round(row.get("amount", 0), 2)} for row in collection.aggregate(pipeline)]
