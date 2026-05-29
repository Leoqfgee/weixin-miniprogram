from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING

from ..repositories.logs import OperationLogRepository
from ..repositories.orders import OrderRepository
from ..repositories.payments import PaymentRepository
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.serializers import serialize_doc, to_object_id


def utc_now():
    return datetime.now(timezone.utc)


class MessageService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.products = ProductRepository(db)

    def send_message(self, sender_id, payload):
        receiver_id = to_object_id(payload.get("receiver_id"), "receiver_id")
        product_id = payload.get("product_id")
        content = (payload.get("content") or "").strip()
        if not content:
            raise ValidationError("参数校验失败", [{"field": "content", "message": "消息内容不能为空"}])
        if str(receiver_id) == str(sender_id):
            raise ConflictError("不能给自己发送消息")
        if not self.users.find_by_id(receiver_id):
            raise NotFoundError("接收方不存在")

        product_object_id = to_object_id(product_id, "product_id") if product_id else None
        user_pair = sorted([str(sender_id), str(receiver_id)])
        conversation_id = "_".join(user_pair + ([str(product_object_id)] if product_object_id else []))
        doc = {
            "conversation_id": conversation_id,
            "type": "private",
            "sender_id": ObjectId(str(sender_id)),
            "receiver_id": receiver_id,
            "product_id": product_object_id,
            "content": content,
            "read_at": None,
            "created_at": utc_now(),
        }
        result = self.db.messages.insert_one(doc)
        return serialize_doc(self.db.messages.find_one({"_id": result.inserted_id}))

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
        return {"items": [serialize_doc(item) for item in self.db.messages.aggregate(pipeline)]}

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
        return {"items": [serialize_doc(item) for item in items]}

    def list_notifications(self, user_id):
        user_object_id = ObjectId(str(user_id))
        items = list(
            self.db.messages.find({"type": "system", "receiver_id": user_object_id})
            .sort("created_at", DESCENDING)
            .limit(50)
        )
        return {"items": [serialize_doc(item) for item in items]}


class ReviewService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)

    def create_review(self, reviewer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(reviewer_id):
            raise ForbiddenError("只有买家可以评价订单")
        if order["status"] != "completed":
            raise ConflictError("只有已完成订单可以评价")
        rating = payload.get("rating")
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValidationError("参数校验失败", [{"field": "rating", "message": "评分必须为 1-5"}])
        content = (payload.get("content") or "").strip()
        doc = {
            "order_id": order_id,
            "reviewer_id": ObjectId(str(reviewer_id)),
            "seller_id": order["seller_id"],
            "rating": rating,
            "content": content,
            "created_at": utc_now(),
        }
        self.db.reviews.update_one(
            {"order_id": order_id, "reviewer_id": ObjectId(str(reviewer_id))},
            {"$set": doc},
            upsert=True,
        )
        return serialize_doc(self.db.reviews.find_one({"order_id": order_id, "reviewer_id": ObjectId(str(reviewer_id))}))


class RefundService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.logs = OperationLogRepository(db)

    def create_refund(self, buyer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(buyer_id):
            raise ForbiddenError("只有买家可以申请退款")
        if order["status"] not in {"paid", "delivering", "completed"}:
            raise ConflictError("当前订单状态不允许申请退款")
        amount = _amount(payload.get("amount"), "amount")
        if amount > float(order["pay_amount"]):
            raise ValidationError("参数校验失败", [{"field": "amount", "message": "退款金额不能超过实付金额"}])
        reason = (payload.get("reason") or "").strip()
        if not reason:
            raise ValidationError("参数校验失败", [{"field": "reason", "message": "退款原因不能为空"}])
        existing = self.db.refunds.find_one({"order_id": order_id, "status": {"$nin": ["rejected", "closed"]}})
        if existing:
            return serialize_doc(existing)
        doc = {
            "order_id": order_id,
            "buyer_id": ObjectId(str(buyer_id)),
            "seller_id": order["seller_id"],
            "amount": amount,
            "reason": reason,
            "evidence_images": payload.get("evidence_images") or [],
            "status": "requested",
            "seller_reason": "",
            "admin_reason": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.refunds.insert_one(doc)
        return serialize_doc(self.db.refunds.find_one({"_id": result.inserted_id}))

    def list_refunds(self, user, args):
        status = args.get("status")
        query = {}
        if status:
            query["status"] = status
        if "admin" not in user.get("roles", []):
            query["$or"] = [{"buyer_id": user["_id"]}, {"seller_id": user["_id"]}]
        items = list(self.db.refunds.find(query).sort("created_at", DESCENDING).limit(50))
        return {"items": [serialize_doc(item) for item in items]}

    def get_refund(self, refund_id, user):
        refund = self._get_refund(refund_id)
        if "admin" not in user.get("roles", []) and str(user["_id"]) not in {str(refund["buyer_id"]), str(refund["seller_id"])}:
            raise ForbiddenError("无权限查看该退款")
        return serialize_doc(refund)

    def seller_handle(self, refund_id, seller_id, payload):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理退款")
        if refund["status"] != "requested":
            raise ConflictError("当前退款状态不允许卖家处理")
        result = payload.get("result")
        if result not in {"approved", "rejected"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "处理结果不合法"}])
        new_status = "approved" if result == "approved" else "arbitration"
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {"$set": {"status": new_status, "seller_reason": (payload.get("reason") or "").strip(), "updated_at": utc_now()}},
        )
        return serialize_doc(self._get_refund(refund["_id"]))

    def admin_arbitrate(self, refund_id, admin_user, payload, trace_id=None):
        refund = self._get_refund(refund_id)
        if refund["status"] not in {"requested", "arbitration"}:
            raise ConflictError("当前退款状态不允许仲裁")
        result = payload.get("result")
        if result not in {"approved", "rejected"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "仲裁结果不合法"}])
        new_status = "approved" if result == "approved" else "rejected"
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {"$set": {"status": new_status, "admin_reason": (payload.get("reason") or "").strip(), "updated_at": utc_now()}},
        )
        self.logs.create(
            actor_id=admin_user["_id"],
            action="refund_arbitrate",
            target_type="refund",
            target_id=refund["_id"],
            detail={"result": result, "reason": payload.get("reason") or ""},
            trace_id=trace_id,
        )
        return serialize_doc(self._get_refund(refund["_id"]))

    def _get_refund(self, refund_id):
        refund = self.db.refunds.find_one({"_id": to_object_id(refund_id, "refund_id")})
        if not refund:
            raise NotFoundError("退款申请不存在")
        return refund


class AiService:
    def __init__(self, db):
        self.db = db

    def product_copy(self, user_id, payload):
        keywords = (payload.get("keywords") or payload.get("title") or "校园闲置").strip()
        title = f"{keywords} 转让"
        description = f"AI mock 建议：{keywords} 成色良好，适合校内自提，可现场验货。"
        doc = {
            "user_id": ObjectId(str(user_id)),
            "mode": "mock",
            "prompt": payload,
            "result": {"title": title, "description": description, "tags": ["校内自提", "闲置转让"]},
            "created_at": utc_now(),
        }
        result = self.db.ai_generation_logs.insert_one(doc)
        return {"ai_draft_id": str(result.inserted_id), **doc["result"]}


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
            "refunds_pending": self.db.refunds.count_documents({"status": {"$in": ["requested", "arbitration"]}}),
        }


def _amount(value, field):
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须是数字"}]) from exc
    if amount <= 0:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须大于 0"}])
    return amount
