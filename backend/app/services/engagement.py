from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING

from ..repositories.escrows import EscrowRepository
from ..repositories.logs import BusinessLogRepository, OperationLogRepository
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
        self.products = ProductRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_review(self, reviewer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(reviewer_id):
            raise ForbiddenError("只有买家可以评价订单")
        if order["status"] != "pending_review":
            raise ConflictError("只有待评价订单可以评价")
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
        review = self.db.reviews.find_one({"order_id": order_id, "reviewer_id": ObjectId(str(reviewer_id))})
        updated_order = self.orders.update_fields(order_id, {"status": "completed", "completed_at": utc_now()})
        for item in self.db.order_items.find({"order_id": order_id}):
            self.products.mark_sold(item["product_id"])
            self.logs.create("product_sold", "product", item["product_id"], ObjectId(str(reviewer_id)), "buyer", "locked", "sold")
        self.logs.create("create_review", "order", order_id, ObjectId(str(reviewer_id)), "buyer", order["status"], updated_order["status"])
        return serialize_doc(review)


class RefundService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.escrows = EscrowRepository(db)
        self.products = ProductRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_refund(self, buyer_id, payload):
        order_id = to_object_id(payload.get("order_id"), "order_id")
        order = self.orders.find_by_id(order_id)
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(buyer_id):
            raise ForbiddenError("只有买家可以申请退款")
        if order["status"] not in {"pending_delivery", "pending_receive"}:
            raise ConflictError("当前订单状态不允许申请退款")
        amount = _amount(payload.get("amount"), "amount")
        if amount > float(order["pay_amount"]):
            raise ValidationError("参数校验失败", [{"field": "amount", "message": "退款金额不能超过实付金额"}])
        reason = (payload.get("reason") or "").strip()
        if not reason:
            raise ValidationError("参数校验失败", [{"field": "reason", "message": "退款原因不能为空"}])
        existing = self.db.refunds.find_one({"order_id": order_id, "status": {"$nin": ["refunded", "closed"]}})
        if existing:
            return serialize_doc(existing)
        self.orders.update_fields(order_id, {"status": "refunding", "pre_refund_status": order["status"]})
        doc = {
            "order_id": order_id,
            "buyer_id": ObjectId(str(buyer_id)),
            "seller_id": order["seller_id"],
            "refund_type": payload.get("refund_type") or "refund_only",
            "amount": amount,
            "reason": reason,
            "description": (payload.get("description") or "").strip(),
            "evidence_images": payload.get("evidence_images") or [],
            "status": "requested",
            "seller_result": "",
            "seller_reason": "",
            "seller_handled_at": None,
            "admin_result": "",
            "admin_reason": "",
            "admin_handled_at": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.refunds.insert_one(doc)
        self.logs.create("apply_refund", "order", order_id, ObjectId(str(buyer_id)), "buyer", order["status"], "refunding", reason)
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

    def seller_agree(self, refund_id, seller_id, payload=None):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理退款")
        if refund["status"] != "requested":
            raise ConflictError("当前退款状态不允许卖家处理")
        order = self.orders.find_by_id(refund["order_id"])
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "seller_agreed",
                    "seller_result": "agreed",
                    "seller_reason": ((payload or {}).get("reason") or "").strip(),
                    "seller_handled_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        self._execute_refund(order, refund, ObjectId(str(seller_id)), "seller", "seller_agree_refund")
        return serialize_doc(self._get_refund(refund["_id"]))

    def seller_reject(self, refund_id, seller_id, payload=None):
        refund = self._get_refund(refund_id)
        if str(refund["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以处理退款")
        if refund["status"] != "requested":
            raise ConflictError("当前退款状态不允许卖家处理")
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "seller_rejected",
                    "seller_result": "rejected",
                    "seller_reason": ((payload or {}).get("reason") or "").strip(),
                    "seller_handled_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        self.logs.create("seller_reject_refund", "refund", refund["_id"], ObjectId(str(seller_id)), "seller", "requested", "seller_rejected", ((payload or {}).get("reason") or ""))
        return serialize_doc(self._get_refund(refund["_id"]))

    def seller_handle(self, refund_id, seller_id, payload):
        result = payload.get("result")
        if result == "approved":
            return self.seller_agree(refund_id, seller_id, payload)
        if result == "rejected":
            return self.seller_reject(refund_id, seller_id, payload)
        raise ValidationError("参数校验失败", [{"field": "result", "message": "处理结果不合法"}])

    def admin_arbitrate(self, refund_id, admin_user, payload, trace_id=None):
        refund = self._get_refund(refund_id)
        order = self.orders.find_by_id(refund["order_id"])
        result = payload.get("result")
        if result not in {"approved", "rejected"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "仲裁结果不合法"}])
        if result == "approved":
            self._execute_refund(order, refund, admin_user["_id"], "admin", "admin_arbitrate")
            return serialize_doc(self._get_refund(refund["_id"]))
        restore_status = order.get("pre_refund_status") or "pending_delivery"
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {"$set": {"status": "closed", "admin_result": "rejected", "admin_reason": (payload.get("reason") or "").strip(), "admin_handled_at": utc_now(), "updated_at": utc_now()}},
        )
        self.orders.update_fields(order["_id"], {"status": restore_status, "pre_refund_status": ""})
        self.logs.create("admin_arbitrate", "refund", refund["_id"], admin_user["_id"], "admin", refund["status"], "closed", payload.get("reason") or "", {"result": result})
        return serialize_doc(self._get_refund(refund["_id"]))

    def _execute_refund(self, order, refund, operator_id, operator_role, action):
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") != "refunded":
            self.payments.update_fields(payment["_id"], {"status": "refunded", "refunded_at": utc_now()})
        escrow = self.escrows.find_by_order(order["_id"])
        if escrow and escrow.get("status") != "refunded":
            self.escrows.update_status(order["_id"], "refunded")
        self.orders.update_fields(order["_id"], {"status": "refunded", "pre_refund_status": ""})
        self.db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": "refunded", "updated_at": utc_now()}})
        for item in self.db.order_items.find({"order_id": order["_id"]}):
            self.products.release_stock(item["product_id"], item["quantity"])
            self.logs.create("product_reopen", "product", item["product_id"], operator_id, operator_role, "locked", "on_sale")
        self.logs.create(action, "refund", refund["_id"], operator_id, operator_role, refund["status"], "refunded")
        self.logs.create("refund_success", "order", order["_id"], operator_id, operator_role, order["status"], "refunded")

    def _get_refund(self, refund_id):
        refund = self.db.refunds.find_one({"_id": to_object_id(refund_id, "refund_id")})
        if not refund:
            raise NotFoundError("退款申请不存在")
        return refund


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
        if force_action not in {"refund", "reject_refund", "partial_refund", "close"}:
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
        else:
            appeal_status = "closed"
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
            self.products.release_stock(item["product_id"], item["quantity"])
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
        data["payment"] = serialize_doc(self.payments.find_by_order(appeal["order_id"])) or {}
        data["escrow"] = serialize_doc(self.escrows.find_by_order(appeal["order_id"])) or {}
        data["delivery"] = serialize_doc(self.db.deliveries.find_one({"order_id": appeal["order_id"]})) or {}
        data["order_items"] = [serialize_doc(item) for item in self.db.order_items.find({"order_id": appeal["order_id"]})]
        if data["order_items"] and not data.get("product_snapshot"):
            data["product_snapshot"] = data["order_items"][0].get("product_snapshot", {})
        return data


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
            "refunds_pending": self.db.refunds.count_documents({"status": {"$in": ["requested", "seller_rejected"]}}),
        }


def _amount(value, field):
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须是数字"}]) from exc
    if amount <= 0:
        raise ValidationError("参数校验失败", [{"field": field, "message": "金额必须大于 0"}])
    return amount
