from bson import ObjectId
from flask import current_app

from ..adapters.payment import get_payment_adapter
from ..repositories.carts import CartRepository
from ..repositories.deliveries import DeliveryRepository
from ..repositories.orders import OrderItemRepository, OrderRepository, utc_now
from ..repositories.payments import PaymentRepository
from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.serializers import serialize_doc, to_object_id


ORDER_STATUSES = {
    "pending_seller_confirm",
    "seller_cancelled",
    "pending_payment",
    "paid",
    "delivering",
    "completed",
    "refunding",
    "refunded",
    "closed",
}
PAYMENT_STATUSES = {"pending", "paid", "failed", "closed"}


class OrderService:
    def __init__(self, db):
        self.db = db
        self.orders = OrderRepository(db)
        self.order_items = OrderItemRepository(db)
        self.payments = PaymentRepository(db)
        self.products = ProductRepository(db)
        self.carts = CartRepository(db)
        self.users = UserRepository(db)
        self.deliveries = DeliveryRepository(db)

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

            order_doc = {
                "buyer_id": buyer_id,
                "seller_id": product_docs[0][0]["seller_id"],
                "status": "pending_seller_confirm",
                "total_amount": total_amount,
                "pay_amount": total_amount,
                "delivery_type": payload.get("delivery_type", "meetup"),
                "meet_location": (payload.get("meet_location") or "").strip(),
                "remark": (payload.get("remark") or "").strip(),
                "closed_reason": "",
                "seller_confirmed_at": None,
                "seller_cancelled_at": None,
                "delivered_at": None,
                "paid_at": None,
                "completed_at": None,
            }
            if idempotency_key:
                order_doc["idempotency_key"] = idempotency_key
            order = self.orders.create(order_doc)
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
            if payload.get("clear_cart", True):
                self.carts.clear_products(buyer_id, [product["_id"] for product, _ in product_docs])
            return self._present_order(order, buyer_id)
        except Exception:
            for product_id, quantity in locked:
                self.products.release_stock(product_id, quantity)
            raise

    def list_orders(self, user_id, args):
        user_id = ObjectId(str(user_id))
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        status = args.get("status")
        if status and status not in ORDER_STATUSES:
            raise ValidationError("参数校验失败", [{"field": "status", "message": "订单状态不合法"}])
        items, total = self.orders.list_for_user(user_id, status=status, page=page, page_size=page_size)
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

    def cancel_order(self, order_id, user_id):
        order = self._get_visible_order(order_id, user_id)
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以取消订单")
        if order["status"] not in {"pending_seller_confirm", "pending_payment"}:
            raise ConflictError("当前订单状态不允许取消")
        self._release_order_stock(order["_id"])
        updated = self.orders.update_fields(order["_id"], {"status": "closed", "closed_reason": "buyer_cancel"})
        payment = self.payments.find_by_order(order["_id"])
        if payment and payment.get("status") == "pending":
            self.payments.update_fields(payment["_id"], {"status": "closed"})
        return self._present_order(updated, ObjectId(str(user_id)))

    def seller_confirm(self, order_id, seller_id):
        order = self._get_visible_order(order_id, seller_id)
        if str(order["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以确认交易")
        if order["status"] != "pending_seller_confirm":
            raise ConflictError("当前订单状态不允许卖家确认")
        adapter = get_payment_adapter(current_app.config.get("PAYMENT_MODE", "mock"))
        payment_meta = adapter.create_payment(order, order["pay_amount"])
        payment = self.payments.find_by_order(order["_id"])
        if not payment:
            payment = self.payments.create_for_order(order["_id"], order["pay_amount"], channel=payment_meta["channel"])
        updated = self.orders.update_fields(
            order["_id"],
            {"status": "pending_payment", "seller_confirmed_at": utc_now()},
        )
        return self._present_order(updated, ObjectId(str(seller_id)), payment=payment)

    def seller_cancel(self, order_id, seller_id, payload=None):
        order = self._get_visible_order(order_id, seller_id)
        if str(order["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以取消交易")
        if order["status"] != "pending_seller_confirm":
            raise ConflictError("当前订单状态不允许卖家取消")
        self._release_order_stock(order["_id"])
        reason = ((payload or {}).get("reason") or "seller_cancel").strip()
        updated = self.orders.update_fields(
            order["_id"],
            {"status": "seller_cancelled", "closed_reason": reason, "seller_cancelled_at": utc_now()},
        )
        return self._present_order(updated, ObjectId(str(seller_id)))

    def _get_visible_order(self, order_id, user_id):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id) and str(order["seller_id"]) != str(user_id):
            raise ForbiddenError("无权限查看该订单")
        return order

    def _release_order_stock(self, order_id):
        for item in self.order_items.list_by_order(order_id):
            self.products.release_stock(item["product_id"], item["quantity"])

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
        if payment is None:
            payment = self.payments.find_by_order(order["_id"])
        data["payment"] = serialize_doc(payment) if payment else None
        data["allowed_actions"] = _order_allowed_actions(order, current_user_id)
        if compact:
            return {
                "id": data["id"],
                "status": data["status"],
                "total_amount": data["total_amount"],
                "items": data["items"],
                "payment": data["payment"],
                "allowed_actions": data["allowed_actions"],
                "created_at": data["created_at"],
            }
        return data


class PaymentService:
    def __init__(self, db):
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)

    def mock_confirm(self, user_id, payload, idempotency_key=None):
        payment = self._find_payment(payload)
        order = self.orders.find_by_id(payment["order_id"])
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以确认支付")
        if payment["status"] == "paid" and order["status"] == "paid":
            return {"payment": serialize_doc(payment), "order_status": order["status"]}
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
        updated_order = self.orders.update_fields(order["_id"], {"status": "paid", "paid_at": paid_at})
        return {"payment": serialize_doc(updated_payment), "order_status": updated_order["status"]}

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
        self.orders = OrderRepository(db)
        self.deliveries = DeliveryRepository(db)

    def seller_deliver(self, order_id, seller_id):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["seller_id"]) != str(seller_id):
            raise ForbiddenError("只有卖家可以确认交付")
        if order["status"] != "paid":
            raise ConflictError("当前订单状态不允许确认交付")
        delivery = self.deliveries.mark_delivering(order["_id"], ObjectId(str(seller_id)))
        updated_order = self.orders.update_fields(order["_id"], {"status": "delivering", "delivered_at": utc_now()})
        return {"order": serialize_doc(updated_order), "delivery": serialize_doc(delivery)}

    def confirm_receipt(self, order_id, user_id):
        order = self.orders.find_by_id(to_object_id(order_id, "order_id"))
        if not order:
            raise NotFoundError("订单不存在")
        if str(order["buyer_id"]) != str(user_id):
            raise ForbiddenError("只有买家可以确认收货")
        if order["status"] != "delivering":
            raise ConflictError("当前订单状态不允许确认收货")
        completed_at = utc_now()
        delivery = self.deliveries.confirm_receipt(order["_id"], ObjectId(str(user_id)))
        updated_order = self.orders.update_fields(
            order["_id"],
            {"status": "completed", "completed_at": completed_at},
        )
        return {"order": serialize_doc(updated_order), "delivery": serialize_doc(delivery)}


def _validate_quantity(value):
    if not isinstance(value, int) or value <= 0:
        raise ValidationError("参数校验失败", [{"field": "quantity", "message": "数量必须是正整数"}])
    return value


def _product_snapshot(product):
    return {
        "product_id": product["_id"],
        "seller_id": product["seller_id"],
        "title": product.get("title"),
        "description": product.get("description"),
        "price": product.get("price"),
        "cover_image": product.get("cover_image"),
        "condition": product.get("condition"),
        "category_id": product.get("category_id"),
    }


def _order_allowed_actions(order, current_user_id):
    is_buyer = str(order["buyer_id"]) == str(current_user_id)
    is_seller = str(order["seller_id"]) == str(current_user_id)
    status = order["status"]
    return {
        "can_seller_confirm": is_seller and status == "pending_seller_confirm",
        "can_seller_cancel": is_seller and status == "pending_seller_confirm",
        "can_seller_deliver": is_seller and status == "paid",
        "can_pay": is_buyer and status == "pending_payment",
        "can_cancel": is_buyer and status in {"pending_seller_confirm", "pending_payment"},
        "can_confirm_receipt": is_buyer and status == "delivering",
        "can_review": is_buyer and status == "completed",
        "can_apply_refund": is_buyer and status in {"paid", "delivering", "completed", "refunding"},
    }
