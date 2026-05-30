from datetime import timedelta

from ..repositories.escrows import EscrowRepository
from ..repositories.logs import BusinessLogRepository
from ..repositories.orders import utc_now
from ..repositories.products import ProductRepository


def run_order_timeout_tasks(db, config):
    """手动执行订单超时任务；动作保持幂等，适合课程阶段用脚本触发。"""
    logs = BusinessLogRepository(db)
    products = ProductRepository(db)
    escrows = EscrowRepository(db)
    now = utc_now()
    summary = {"closed_payment_orders": 0, "auto_received_orders": 0, "refund_timeout_logs": 0}

    payment_deadline = now - timedelta(minutes=config["ORDER_PAYMENT_TIMEOUT_MINUTES"])
    for order in db.orders.find({"status": "pending_payment", "created_at": {"$lte": payment_deadline}}):
        for item in db.order_items.find({"order_id": order["_id"]}):
            products.release_stock(item["product_id"], item["quantity"])
            logs.create("product_reopen", "product", item["product_id"], None, "system", "locked", "on_sale", "payment_timeout")
        db.orders.update_one(
            {"_id": order["_id"], "status": "pending_payment"},
            {"$set": {"status": "closed", "closed_reason": "payment_timeout", "updated_at": now}},
        )
        logs.create("timeout_close_order", "order", order["_id"], None, "system", "pending_payment", "closed", "payment_timeout")
        summary["closed_payment_orders"] += 1

    receive_deadline = now - timedelta(days=config["ORDER_AUTO_RECEIVE_DAYS"])
    for order in db.orders.find({"status": "pending_receive", "delivered_at": {"$lte": receive_deadline}}):
        db.orders.update_one(
            {"_id": order["_id"], "status": "pending_receive"},
            {"$set": {"status": "pending_review", "received_at": now, "updated_at": now}},
        )
        escrow = escrows.update_status(order["_id"], "settled")
        if escrow:
            logs.create("escrow_settle", "escrow", escrow["_id"], None, "system", "holding", "settled", "auto_receive")
        logs.create("buyer_confirm_receive", "order", order["_id"], None, "system", "pending_receive", "pending_review", "auto_receive")
        summary["auto_received_orders"] += 1

    refund_deadline = now - timedelta(hours=config["REFUND_SELLER_TIMEOUT_HOURS"])
    for refund in db.refunds.find({"status": "requested", "created_at": {"$lte": refund_deadline}}):
        logs.create("refund_timeout", "refund", refund["_id"], None, "system", "requested", "requested", "seller_timeout")
        summary["refund_timeout_logs"] += 1

    return summary
