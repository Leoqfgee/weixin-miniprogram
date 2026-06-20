from uuid import uuid4

from bson import ObjectId
from flask import current_app

from ..adapters.payment import get_payment_adapter
from ..domain.campus import normalize_campus
from ..domain.categories import category_name, normalize_category_code
from ..repositories.deliveries import DeliveryRepository
from ..repositories.escrows import EscrowRepository
from ..repositories.logs import BusinessLogRepository
from ..repositories.orders import OrderItemRepository, OrderRepository, utc_now
from ..repositories.payments import PaymentRepository
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.images import normalize_image_url
from ..utils.serializers import serialize_doc, to_object_id


ORDER_STATUSES = {
    "pending_payment",
    "pending_delivery",
    "pending_receive",
    "pending_review",
    "completed",
    "closed",
    "refunding",
    "refunded",
}
PAYMENT_STATUSES = {"pending", "paid", "failed", "refunded"}
DELIVERY_TYPES = {"offline_meetup", "campus_pickup", "campus_delivery", "express"}
ORDER_STATUS_TEXT = {
    "pending_payment": "待付款",
    "pending_delivery": "待发货",
    "pending_receive": "待收货",
    "pending_review": "待评价",
    "completed": "交易完成",
    "closed": "已关闭",
    "refunding": "售后中",
    "refunded": "已退款",
}
ORDER_STATUS_TIPS = {
    "pending_payment": "请尽快完成付款，超时后订单将自动关闭",
    "pending_delivery": "买家已付款，等待卖家交付",
    "pending_receive": "卖家已交付，请买家确认收货",
    "pending_review": "交易已确认收货，双方可进行评价",
    "completed": "交易已完成",
    "closed": "订单已关闭",
    "refunding": "订单售后处理中",
    "refunded": "订单已退款",
}
REFUND_STATUS_TEXT = {
    "requested": "待处理",
    "seller_agreed": "退款中",
    "refunding": "退款中",
    "refunded": "已退款",
    "partial_refunded": "已退款",
    "seller_rejected": "已拒绝",
    "rejected": "已拒绝",
    "closed": "已关闭",
}
REFUND_STATUS_GROUP = {
    "requested": "pending",
    "seller_agreed": "refunding",
    "refunding": "refunding",
    "refunded": "refunded",
    "partial_refunded": "refunded",
    "seller_rejected": "rejected",
    "rejected": "rejected",
    "closed": "closed",
}


class OrderService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.order_items = OrderItemRepository(db)
        self.payments = PaymentRepository(db)
        self.escrows = EscrowRepository(db)
        self.products = ProductRepository(db)
        self.users = UserRepository(db)
        self.deliveries = DeliveryRepository(db)
        self.logs = BusinessLogRepository(db)

    def create_order(self, buyer_id, payload, idempotency_key=None):
        buyer_id = ObjectId(str(buyer_id))
        idempotency_key = idempotency_key or payload.get("idempotency_key")
        if idempotency_key:
            existing = self.orders.find_by_idempotency_key(buyer_id, idempotency_key)
            if existing:
                return self.get_order(existing["_id"], buyer_id)

        lines = self._resolve_order_lines(payload)
        if not lines:
            raise ValidationError("参数校验失败", [{"field": "items", "message": "订单商品不能为空"}])

        locked = []
        try:
            product_docs = []
            seller_ids = set()
            total_amount = 0
            for line in lines:
                product = self.products.find_by_id(line["product_id"])
                if not product:
                    raise NotFoundError("商品不存在")
                if product.get("status") != "on_sale":
                    raise ConflictError("商品当前不可购买")
                if str(product.get("seller_id")) == str(buyer_id):
                    raise ForbiddenError("不能购买自己的商品")
                if product.get("stock", 0) < line["quantity"]:
                    raise ConflictError("商品库存不足")
                seller_ids.add(str(product["seller_id"]))
                product_docs.append((product, line["quantity"]))
                total_amount = round(total_amount + product["price"] * line["quantity"], 2)

            if len(seller_ids) != 1:
                raise ValidationError("参数校验失败", [{"field": "items", "message": "暂只支持同一卖家的商品合并下单"}])

            for product, quantity in product_docs:
                if not self.products.lock_stock(product["_id"], quantity):
                    raise ConflictError("商品库存不足或已下架")
                locked.append((product["_id"], quantity))
                self._log("product_locked", "product", product["_id"], buyer_id, "buyer", "on_sale", "locked")

            delivery_type = _normalize_delivery_type(payload.get("delivery_type", "offline_meetup"))
            shipping_address = self._resolve_shipping_address(buyer_id, payload) if delivery_type == "express" else None
            order_doc = {
                "order_no": f"ORD{utc_now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:8].upper()}",
                "buyer_id": buyer_id,
                "seller_id": product_docs[0][0]["seller_id"],
                "product_id": product_docs[0][0]["_id"],
                "status": "pending_payment",
                "pre_refund_status": "",
                "total_amount": total_amount,
                "pay_amount": total_amount,
                "delivery_type": delivery_type,
                "meet_location": (payload.get("meet_location") or "").strip(),
                "shipping_address": shipping_address,
                "remark": (payload.get("remark") or "").strip(),
                "closed_reason": "",
                "paid_at": None,
                "delivered_at": None,
                "received_at": None,
                "completed_at": None,
            }
            if idempotency_key:
                order_doc["idempotency_key"] = idempotency_key
            order = self.orders.create(order_doc)
            self._log("create_order", "order", order["_id"], buyer_id, "buyer", None, "pending_payment")
            _append_order_system_message(self.db, order, "买家已提交订单，等待付款", "order_created")
            order_items = []
            for product, quantity in product_docs:
                order_items.append(
                    {
                        "order_id": order["_id"],
                        "product_id": product["_id"],
                        "seller_id": product["seller_id"],
                        "quantity": quantity,
                        "unit_price": product["price"],
                        "total_amount": round(product["price"] * quantity, 2),
                        "product_snapshot": _product_snapshot(product),
                        "created_at": utc_now(),
                    }
                )
            self.order_items.create_many(order_items)

            return self._present_order(order, buyer_id)
        except Exception:
            for product_id, quantity in locked:
                self.products.release_stock(product_id, quantity)
                self._log("product_reopen", "product", product_id, buyer_id, "buyer", "locked", "on_sale", "create_order_failed")
            raise

    def list_orders(self, user_id, args):
        user_id = ObjectId(str(user_id))
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        status = args.get("status")
        role = args.get("role")
        if status and status not in ORDER_STATUSES:
            raise ValidationError("参数校验失败", [{"field": "status", "message": "订单状态不合法"}])
        if role and role not in {"buyer", "seller"}:
            raise ValidationError("参数校验失败", [{"field": "role", "message": "角色筛选不合法"}])
        items, total = self.orders.list_for_user(user_id, status=status, page=page, page_size=page_size, role=role)
        return {
            "items": [self._present_order(item, user_id, compact=True) for item in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def get_order(self, order_id, user_id):
        order = self._get_visible_order(order_id, user_id)
        return self._present_order(order, ObjectId(str(user_id)))

    def buyer_cancel(self, order_id, user_id, reason="buyer_cancel"):
        order = self._get_visible_order(order_id, user_id)
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以取消自己的订单")
        if order["status"] != "pending_payment":
            raise ConflictError("当前订单状态不允许取消")
        self._release_order_stock(order["_id"], ObjectId(str(user_id)), "buyer")
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") == "pending":
            self.payments.update_fields(payment["_id"], {"status": "failed"})
        updated = self._transition(order, "closed", ObjectId(str(user_id)), "buyer", "cancel_order", reason)
        _append_order_system_message(self.db, updated, "买家已取消订单", "order_closed")
        return self._present_order(updated, ObjectId(str(user_id)))

    def close_timeout(self, order_id, reason="payment_timeout"):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if order["status"] != "pending_payment":
            return self._present_order(order, order["buyer_id"])
        self._release_order_stock(order["_id"], None, "system")
        updated = self._transition(order, "closed", None, "system", "timeout_close_order", reason)
        return self._present_order(updated, order["buyer_id"])

    def seller_cancel_and_refund(self, order_id, seller_id, reason="seller_cancel"):
        order = self._get_visible_order(order_id, seller_id)
        if str(order["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以取消交易")
        if order["status"] != "pending_delivery":
            raise ConflictError("当前订单状态不允许卖家取消")
        operator_id = ObjectId(str(seller_id))
        refund = self._ensure_refund(
            order,
            operator_id,
            "seller",
            "卖家取消交易",
            refund_type="refund_only",
            status="seller_agreed",
            seller_result="agreed",
            seller_reason=reason,
        )
        refunding_order = self._transition(order, "refunding", operator_id, "seller", "seller_cancel_and_refund", reason)
        refunded_order = self._execute_refund(refunding_order, refund, operator_id, "seller", "seller_cancel_and_refund", reason)
        _append_order_system_message(self.db, refunded_order, "卖家取消交易，退款已处理", "seller_cancelled")
        return self._present_order(refunded_order, operator_id)

    def _get_visible_order(self, order_id, user_id):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id) and str(order["seller_id"]) != str(user_id):
            raise ForbiddenError("无权限查看该订单")
        return order

    def _release_order_stock(self, order_id, operator_id=None, operator_role="system"):
        for item in self.order_items.list_by_order(order_id):
            self.products.release_stock(item["product_id"], item["quantity"])
            self._log("product_reopen", "product", item["product_id"], operator_id, operator_role, "locked", "on_sale")

    def _close_products_after_refund(self, order_id, operator_id=None, operator_role="system"):
        for item in self.order_items.list_by_order(order_id):
            self.products.mark_off_shelf_after_refund(item["product_id"])
            self._log("product_off_shelf_after_refund", "product", item["product_id"], operator_id, operator_role, "locked", "off_shelf")

    def _ensure_refund(
        self,
        order,
        operator_id,
        operator_role,
        reason,
        refund_type="refund_only",
        status="requested",
        seller_result="",
        seller_reason="",
    ):
        existing = self.db.refunds.find_one({"order_id": order["_id"], "status": {"$nin": ["refunded", "closed"]}})
        if existing:
            return existing
        now = utc_now()
        doc = {
            "order_id": order["_id"],
            "product_id": order.get("product_id"),
            "buyer_id": order["buyer_id"],
            "seller_id": order["seller_id"],
            "applicant_id": operator_id,
            "refund_type": refund_type,
            "amount": order["pay_amount"],
            "request_amount": order["pay_amount"],
            "final_refund_amount": order["pay_amount"] if status in {"seller_agreed", "refunded"} else None,
            "reason": reason,
            "description": reason,
            "evidence_images": [],
            "status": status,
            "seller_result": seller_result,
            "seller_reason": seller_reason,
            "seller_response": seller_reason,
            "seller_handled_at": now if seller_result else None,
            "admin_result": "",
            "admin_decision": "",
            "admin_reason": "",
            "admin_handled_at": None,
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.refunds.insert_one(doc)
        self._log("apply_refund", "order", order["_id"], operator_id, operator_role, order["status"], "refunding", reason)
        return self.db.refunds.find_one({"_id": result.inserted_id})

    def _execute_refund(self, order, refund, operator_id, operator_role, action, reason):
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") != "refunded":
            self.payments.update_fields(payment["_id"], {"status": "refunded", "refunded_at": utc_now()})
        escrow = self.escrows.find_by_order(order["_id"])
        if escrow and escrow.get("status") != "refunded":
            self.escrows.update_status(order["_id"], "refunded")
        self.db.refunds.update_one(
            {"_id": refund["_id"]},
            {
                "$set": {
                    "status": "refunded",
                    "final_refund_amount": refund.get("final_refund_amount") or refund.get("amount") or order.get("pay_amount"),
                    "seller_result": refund.get("seller_result") or "agreed",
                    "seller_handled_at": refund.get("seller_handled_at") or utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        self._close_products_after_refund(order["_id"], operator_id, operator_role)
        updated_order = self.orders.update_fields(order["_id"], {"status": "refunded", "pre_refund_status": ""})
        self._log(action, "refund", refund["_id"], operator_id, operator_role, refund.get("status"), "refunded", reason)
        self._log("refund_success", "order", order["_id"], operator_id, operator_role, order["status"], "refunded", reason)
        return updated_order

    def _mark_products_sold(self, order_id, operator_id):
        for item in self.order_items.list_by_order(order_id):
            self.products.mark_sold(item["product_id"])
            self._log("product_sold", "product", item["product_id"], operator_id, "buyer", "locked", "sold")

    def _transition(self, order, to_status, operator_id, operator_role, action, reason="", extra=None):
        from_status = order["status"]
        updated = self.orders.update_fields(order["_id"], {"status": to_status, "closed_reason": reason if to_status == "closed" else order.get("closed_reason", "")})
        self._log(action, "order", order["_id"], operator_id, operator_role, from_status, to_status, reason, extra)
        return updated

    def _log(self, action, target_type, target_id, operator_id, operator_role, from_status=None, to_status=None, reason="", extra=None):
        self.logs.create(action, target_type, target_id, operator_id, operator_role, from_status, to_status, reason, extra)

    def _resolve_order_lines(self, payload):
        if payload.get("items"):
            raw_items = payload.get("items")
            if not isinstance(raw_items, list):
                raise ValidationError("参数校验失败", [{"field": "items", "message": "items 必须是数组"}])
            return [
                {
                    "product_id": to_object_id(item.get("product_id"), "product_id"),
                    "quantity": _validate_quantity(item.get("quantity", 1)),
                }
                for item in raw_items
            ]
        return [
            {
                "product_id": to_object_id(payload.get("product_id"), "product_id"),
                "quantity": _validate_quantity(payload.get("quantity", 1)),
            }
        ]

    def _present_order(self, order, current_user_id, payment=None, compact=False):
        data = serialize_doc(order)
        items = [serialize_doc(item) for item in self.order_items.list_by_order(order["_id"])]
        data["items"] = items
        data["product_snapshot"] = items[0]["product_snapshot"] if items else {}
        if data["product_snapshot"].get("cover_image"):
            data["product_snapshot"]["cover_image"] = normalize_image_url(data["product_snapshot"].get("cover_image"))
        if payment is None:
            payment = self.payments.find_by_order(order["_id"])
        data["payment"] = serialize_doc(payment) if payment else None
        escrow = self.escrows.find_by_order(order["_id"])
        data["escrow"] = serialize_doc(escrow) if escrow else None
        delivery = self.deliveries.find_by_order(order["_id"])
        data["delivery"] = serialize_doc(delivery) if delivery else None
        refund = self.db.refunds.find_one({"order_id": order["_id"]}, sort=[("created_at", -1)])
        data["refund"] = serialize_doc(refund) if refund else None
        if data["refund"]:
            data["refund"]["status_text"] = REFUND_STATUS_TEXT.get(refund.get("status"), refund.get("status", ""))
            data["refund"]["status_group"] = REFUND_STATUS_GROUP.get(refund.get("status"), refund.get("status", ""))
        appeal = self.db.appeals.find_one({"order_id": order["_id"]}, sort=[("created_at", -1)])
        data["appeal"] = serialize_doc(appeal) if appeal else None
        reviews = list(self.db.reviews.find({"order_id": order["_id"]}).sort("created_at", 1))
        data["reviews"] = [serialize_doc(item) for item in reviews]
        data["buyer"] = self._party(order["buyer_id"])
        data["seller"] = self._party(order["seller_id"])
        current_user_id = ObjectId(str(current_user_id))
        is_buyer = str(order["buyer_id"]) == str(current_user_id)
        data["current_role"] = "buyer" if is_buyer else "seller"
        data["status_text"] = ORDER_STATUS_TEXT.get(order.get("status"), order.get("status", ""))
        data["status_tip"] = ORDER_STATUS_TIPS.get(order.get("status"), "")
        data["conversation_id"] = _order_conversation_id(order)
        contact_party = data["seller"] if is_buyer else data["buyer"]
        data["contact_user"] = contact_party
        data["contact_label"] = "联系卖家" if is_buyer else "联系买家"
        data["allowed_actions"] = _order_allowed_actions(
            order, current_user_id, payment, refund, {str(item["reviewer_id"]) for item in reviews}
        )
        if compact:
            return {
                "id": data["id"],
                "order_no": data.get("order_no"),
                "status": data["status"],
                "total_amount": data["total_amount"],
                "items": data["items"],
                "payment": data["payment"],
                "escrow": data["escrow"],
                "allowed_actions": data["allowed_actions"],
                "buyer": data["buyer"],
                "seller": data["seller"],
                "current_role": data["current_role"],
                "status_text": data["status_text"],
                "status_tip": data["status_tip"],
                "conversation_id": data["conversation_id"],
                "contact_user": data["contact_user"],
                "contact_label": data["contact_label"],
                "shipping_address": data.get("shipping_address"),
                "created_at": data["created_at"],
            }
        return data

    def _party(self, user_id):
        profile = self.users.find_profile(user_id) or {}
        user = self.users.find_by_id(user_id) or {}
        phone = user.get("phone") or profile.get("contact_phone") or ""
        return {
            "id": str(user_id),
            "nickname": profile.get("nickname", "校园用户"),
            "avatar": profile.get("avatar") or profile.get("avatar_url", ""),
            "campus": normalize_campus(profile.get("campus"), ""),
            "phone_masked": _mask_phone(phone),
        }

    def _resolve_shipping_address(self, buyer_id, payload):
        address_payload = payload.get("shipping_address") if isinstance(payload.get("shipping_address"), dict) else {}
        address_id = payload.get("shipping_address_id") or address_payload.get("id")
        if address_id:
            address = self.db.addresses.find_one(
                {"_id": to_object_id(address_id, "shipping_address_id"), "user_id": buyer_id}
            )
            if not address:
                raise NotFoundError("收货地址不存在或已删除")
            return _shipping_address_snapshot(serialize_doc(address))
        return _shipping_address_snapshot(payload.get("shipping_address"))


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.escrows = EscrowRepository(db)
        self.logs = BusinessLogRepository(db)

    def prepay(self, user_id, payload, idempotency_key=None):
        order = self.orders.find_by_id(to_object_id(payload.get("order_id"), "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以发起支付")
        if order["status"] != "pending_payment":
            raise ConflictError("当前订单状态不允许支付")
        adapter = get_payment_adapter(current_app.config.get("PAYMENT_MODE", "mock"))
        payment_meta = adapter.create_payment(order, order["pay_amount"])
        payment = self.payments.create_for_order(order, order["pay_amount"], channel=payment_meta["channel"], idempotency_key=idempotency_key)
        return {"payment": serialize_doc(payment), "mock_pay_params": {"order_id": str(order["_id"]), "amount": order["pay_amount"]}}

    def mock_confirm(self, user_id, payload, idempotency_key=None):
        payment = self._find_payment(payload)
        order = self.orders.find_by_id(payment["order_id"])
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以确认支付")
        if payment["status"] == "paid" and order["status"] in {"pending_delivery", "pending_receive", "pending_review", "completed"}:
            escrow = self.escrows.create_holding(order)
            return {"payment": serialize_doc(payment), "escrow": serialize_doc(escrow), "order_status": order["status"]}
        if order["status"] != "pending_payment" or payment["status"] != "pending":
            raise ConflictError("当前订单或支付单状态不允许支付")

        adapter = get_payment_adapter("mock")
        confirm_result = adapter.confirm_payment(payment, payload)
        mock_result = confirm_result["raw"].get("mock_result", "success")
        if mock_result not in {"success", "failed"}:
            raise ValidationError("参数校验失败", [{"field": "mock_result", "message": "模拟支付结果不合法"}])
        if round(payment["amount"], 2) != round(order["pay_amount"], 2):
            raise ConflictError("支付金额与订单金额不一致")

        if not confirm_result["success"]:
            updated_payment = self.payments.update_fields(payment["_id"], {"status": "failed"})
            return {"payment": serialize_doc(updated_payment), "order_status": order["status"]}

        paid_at = utc_now()
        updated_payment = self.payments.update_fields(payment["_id"], {"status": "paid", "paid_at": paid_at})
        updated_order = self.orders.update_fields(order["_id"], {"status": "pending_delivery", "paid_at": paid_at})
        self.logs.create("pay_success", "order", order["_id"], order["buyer_id"], "buyer", "pending_payment", "pending_delivery")
        escrow = self.escrows.create_holding(updated_order)
        _append_order_system_message(self.db, updated_order, "买家已付款，等待卖家交付", "paid")
        self.logs.create("create_escrow", "escrow", escrow["_id"], order["buyer_id"], "buyer", None, "holding", extra={"order_id": order["_id"]})
        return {"payment": serialize_doc(updated_payment), "escrow": serialize_doc(escrow), "order_status": updated_order["status"]}

    def refund_payment(self, order, operator_id, operator_role, reason="refund_success"):
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment["status"] != "refunded":
            self.payments.update_fields(payment["_id"], {"status": "refunded", "refunded_at": utc_now()})
        escrow = self.escrows.find_by_order(order["_id"])
        if escrow and escrow["status"] != "refunded":
            self.escrows.update_status(order["_id"], "refunded")
        self.logs.create("refund_success", "order", order["_id"], operator_id, operator_role, order["status"], "refunded", reason)

    def _find_payment(self, payload):
        if payload.get("payment_id"):
            payment = self.payments.find_by_id(to_object_id(payload.get("payment_id"), "payment_id"))
        elif payload.get("order_id"):
            payment = self.payments.find_by_order(to_object_id(payload.get("order_id"), "order_id"))
        else:
            raise ValidationError("参数校验失败", [{"field": "payment_id", "message": "payment_id 或 order_id 必填"}])
        if not payment:
            raise NotFoundError("支付单不存在")
        return payment


class DeliveryService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.deliveries = DeliveryRepository(db)
        self.escrows = EscrowRepository(db)
        self.logs = BusinessLogRepository(db)

    def get_delivery(self, order_id, user_id):
        order = self._get_visible_order(order_id, user_id)
        delivery = self.deliveries.find_by_order(order["_id"])
        if not delivery:
            raise NotFoundError("交付信息不存在")
        return serialize_doc(delivery)

    def seller_deliver(self, order_id, seller_id, payload=None):
        payload = payload or {}
        order = self._get_visible_order(order_id, seller_id)
        if str(order["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以确认交付")
        if order["status"] != "pending_delivery":
            raise ConflictError("当前订单状态不允许确认交付")
        delivery_type = _normalize_delivery_type(payload.get("delivery_type") or order.get("delivery_type") or "offline_meetup")
        _validate_delivery_payload(delivery_type, payload)
        delivery = self.deliveries.mark_delivering(order, ObjectId(str(seller_id)), payload, delivery_type)
        updated_order = self.orders.update_fields(order["_id"], {"status": "pending_receive", "delivered_at": utc_now()})
        self.logs.create("seller_deliver", "order", order["_id"], ObjectId(str(seller_id)), "seller", "pending_delivery", "pending_receive", payload.get("delivery_note") or "")
        _append_order_system_message(self.db, updated_order, "卖家已交付/发货，等待买家确认收货", "delivered")
        return {"order": serialize_doc(updated_order), "delivery": serialize_doc(delivery)}

    def buyer_confirm(self, order_id, user_id):
        order = self._get_visible_order(order_id, user_id)
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以确认收货")
        if order["status"] != "pending_receive":
            raise ConflictError("当前订单状态不允许确认收货")
        delivery = self.deliveries.confirm_receipt(order["_id"], ObjectId(str(user_id)))
        escrow = self.escrows.update_status(order["_id"], "settled")
        self.logs.create("escrow_settle", "escrow", escrow["_id"], ObjectId(str(user_id)), "buyer", "holding", "settled", extra={"order_id": order["_id"]})
        updated_order = self.orders.update_fields(order["_id"], {"status": "pending_review", "received_at": utc_now()})
        self.logs.create("buyer_confirm_receive", "order", order["_id"], ObjectId(str(user_id)), "buyer", "pending_receive", "pending_review")
        _append_order_system_message(self.db, updated_order, "买家已确认收货，双方可以评价", "received")
        return {"order": serialize_doc(updated_order), "delivery": serialize_doc(delivery), "escrow": serialize_doc(escrow)}

    def buyer_reject(self, order_id, user_id, payload=None):
        payload = payload or {}
        order = self._get_visible_order(order_id, user_id)
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以拒绝收货")
        if order["status"] != "pending_receive":
            raise ConflictError("当前订单状态不允许拒绝收货")
        updated_order = self.orders.update_fields(order["_id"], {"status": "refunding", "pre_refund_status": "pending_receive"})
        operator_id = ObjectId(str(user_id))
        reason = (payload.get("reason") or "买家拒绝收货").strip()
        self._ensure_reject_refund(order, operator_id, reason, payload)
        self.logs.create("buyer_reject_receive", "order", order["_id"], operator_id, "buyer", "pending_receive", "refunding", reason)
        return serialize_doc(updated_order)

    def _ensure_reject_refund(self, order, buyer_id, reason, payload):
        existing = self.db.refunds.find_one({"order_id": order["_id"], "status": {"$nin": ["refunded", "closed"]}})
        if existing:
            return existing
        now = utc_now()
        doc = {
            "order_id": order["_id"],
            "product_id": order.get("product_id"),
            "buyer_id": buyer_id,
            "seller_id": order["seller_id"],
            "applicant_id": buyer_id,
            "refund_type": payload.get("refund_type") or "refund_only",
            "amount": order["pay_amount"],
            "request_amount": order["pay_amount"],
            "final_refund_amount": None,
            "reason": reason,
            "description": (payload.get("description") or reason).strip(),
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
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.refunds.insert_one(doc)
        self.logs.create("apply_refund", "order", order["_id"], buyer_id, "buyer", "pending_receive", "refunding", reason)
        return self.db.refunds.find_one({"_id": result.inserted_id})

    def _get_visible_order(self, order_id, user_id):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id) and str(order["seller_id"]) != str(user_id):
            raise ForbiddenError("无权限查看该订单")
        return order


def _validate_quantity(value):
    if not isinstance(value, int) or value <= 0:
        raise ValidationError("参数校验失败", [{"field": "quantity", "message": "数量必须是正整数"}])
    return value


def _product_snapshot(product):
    category = normalize_category_code(product.get("category")) or "other"
    return {
        "product_id": product["_id"],
        "seller_id": product["seller_id"],
        "title": product.get("title"),
        "description": product.get("description"),
        "price": product.get("price"),
        "cover_image": normalize_image_url(product.get("cover_image")),
        "condition": product.get("condition"),
        "category_id": product.get("category_id"),
        "category": category,
        "category_name": product.get("category_name") or category_name(category),
        "category_source": product.get("category_source") or "legacy",
        "defect_note": product.get("defect_note", ""),
    }


def _normalize_delivery_type(value):
    aliases = {"meetup": "offline_meetup"}
    delivery_type = aliases.get(value, value)
    if delivery_type not in DELIVERY_TYPES:
        raise ValidationError("参数校验失败", [{"field": "delivery_type", "message": "交付方式不合法"}])
    return delivery_type


def _validate_delivery_payload(delivery_type, payload):
    if delivery_type == "offline_meetup" and not (payload.get("meet_location") or payload.get("delivery_note")):
        raise ValidationError("参数校验失败", [{"field": "meet_location", "message": "校内面交需填写地点或说明"}])
    if delivery_type == "campus_pickup" and not (payload.get("pickup_location") or payload.get("delivery_note")):
        raise ValidationError("参数校验失败", [{"field": "pickup_location", "message": "校园自提需填写地点或说明"}])
    if delivery_type == "campus_delivery" and not (payload.get("campus_address") or payload.get("delivery_note")):
        raise ValidationError("参数校验失败", [{"field": "campus_address", "message": "校内送达需填写地址或说明"}])
    if delivery_type == "express" and (not payload.get("express_company") or not payload.get("tracking_no")):
        raise ValidationError("参数校验失败", [{"field": "tracking_no", "message": "快递方式需填写快递公司和单号"}])


def _order_allowed_actions(order, current_user_id, payment=None, refund=None, reviewer_ids=None):
    is_buyer = str(order["buyer_id"]) == str(current_user_id)
    is_seller = str(order["seller_id"]) == str(current_user_id)
    status = order["status"]
    reviewer_ids = reviewer_ids or set()
    already_reviewed = str(current_user_id) in reviewer_ids
    actions = []
    if is_buyer:
        actions_by_status = {
            "pending_payment": ["pay", "cancel_order"],
            "pending_delivery": ["contact_seller", "apply_refund"],
            "pending_receive": ["confirm_receive", "reject_receive", "apply_refund", "contact_seller"],
            "pending_review": ([] if already_reviewed else ["create_review"]) + ["apply_after_sale", "view_after_sale"],
            "completed": ([] if already_reviewed else ["create_review"]) + ["view_review", "apply_after_sale"],
            "refunding": ["view_refund"],
            "refunded": ["view_refund_result"],
            "closed": ["view_close_reason"],
        }
        actions.extend(actions_by_status.get(status, []))
        if status == "refunding" and refund and refund.get("status") == "seller_rejected":
            actions.append("apply_appeal")
    if is_seller:
        actions_by_status = {
            "pending_delivery": ["seller_deliver", "seller_cancel_and_refund", "contact_buyer"],
            "pending_receive": ["view_delivery", "contact_buyer"],
            "refunding": ["agree_refund", "reject_refund", "upload_evidence"],
            "pending_review": ([] if already_reviewed else ["create_review"]) + ["contact_buyer"],
            "completed": ([] if already_reviewed else ["create_review"]) + ["view_review"],
        }
        actions.extend(actions_by_status.get(status, []))
    return {
        "actions": actions,
        "can_pay": "pay" in actions,
        "can_cancel": "cancel_order" in actions,
        "can_seller_deliver": "seller_deliver" in actions,
        "can_seller_cancel_and_refund": "seller_cancel_and_refund" in actions,
        "can_confirm_receipt": "confirm_receive" in actions,
        "can_reject_receive": "reject_receive" in actions,
        "can_review": "create_review" in actions,
        "can_apply_refund": "apply_refund" in actions or "apply_after_sale" in actions,
        "can_apply_appeal": "apply_appeal" in actions and refund and refund.get("status") == "seller_rejected",
        "can_agree_refund": "agree_refund" in actions,
        "can_reject_refund": "reject_refund" in actions,
    }


def _shipping_address_snapshot(value):
    if not isinstance(value, dict):
        raise ValidationError("参数校验失败", [{"field": "shipping_address", "message": "邮寄订单必须选择收货地址"}])
    name = (value.get("name") or "").strip()
    phone = (value.get("phone") or "").strip()
    address = (value.get("address") or "").strip()
    if not name or not phone or not address:
        raise ValidationError("参数校验失败", [{"field": "shipping_address", "message": "收货地址信息不完整"}])
    return {"id": str(value.get("id") or ""), "name": name, "phone": phone, "address": address}


def _append_order_system_message(db, order, content, action):
    conversation_id = _order_conversation_id(order)
    seller_actions = {"order_created", "paid", "received", "order_closed"}
    sender_id = order["buyer_id"] if action in seller_actions else order["seller_id"]
    receiver_id = order["seller_id"] if action in seller_actions else order["buyer_id"]
    db.messages.insert_one(
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
            "image_url": "",
            "read_at": None,
            "created_at": utc_now(),
        }
    )


def _order_conversation_id(order):
    user_pair = sorted([str(order["buyer_id"]), str(order["seller_id"])])
    return "_".join(user_pair + [str(order["product_id"])])


def _mask_phone(phone):
    value = str(phone or "")
    if len(value) < 7:
        return value
    return f"{value[:3]}****{value[-4:]}"
