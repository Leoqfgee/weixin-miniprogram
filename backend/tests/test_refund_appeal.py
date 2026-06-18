from bson import ObjectId

from test_phase3_trade_flow import auth_headers, create_on_sale_product, create_order, pay_order, setup_flow


def create_refundable_order(client, seller_token, buyer_token, admin_token):
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)
    pay_order(client, buyer_token, order["id"])
    client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(seller_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口"},
    )
    return order


def test_refund_agree_sets_order_payment_and_escrow_refunded():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品问题", "refund_type": "refund_only"},
    )
    assert refund.status_code == 201
    refund_id = refund.get_json()["data"]["id"]
    agree = client.post(f"/api/v1/refunds/{refund_id}/seller-agree", headers=auth_headers(seller_token))
    assert agree.status_code == 200
    assert agree.get_json()["data"]["status"] == "refunded"

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert detail["status"] == "refunded"
    assert detail["payment"]["status"] == "refunded"
    assert detail["escrow"]["status"] == "refunded"


def test_refund_apply_evidence_images_are_saved():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    evidence = ["/uploads/refund/a.png", "/uploads/refund/b.png"]
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={
            "order_id": order["id"],
            "amount": 20,
            "reason": "商品瑕疵",
            "refund_type": "refund_only",
            "evidence_images": evidence,
        },
    )
    assert refund.status_code == 201
    assert refund.get_json()["data"]["evidence_images"] == evidence


def test_refund_list_detail_and_unread_badge_flow():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品有瑕疵", "refund_type": "return_and_refund"},
    )
    assert refund.status_code == 201
    refund_id = refund.get_json()["data"]["id"]

    refund_doc = app.db.refunds.find_one({"_id": ObjectId(refund_id)})
    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["buyer_id"],
        "system_action": "refund_requested",
        "read_at": None,
    }) == 0
    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["seller_id"],
        "system_action": "refund_requested",
        "read_at": None,
    }) == 1

    seller_list = client.get("/api/v1/refunds?role=seller&status=pending", headers=auth_headers(seller_token))
    assert seller_list.status_code == 200
    item = seller_list.get_json()["data"]["items"][0]
    assert item["id"] == refund_id
    assert item["status_text"] == "待处理"
    assert item["status_group"] == "pending"
    assert item["after_sale_no"].startswith("SH")
    assert item["product"]["title"]
    assert item["buyer"]["nickname"]
    assert "phone_masked" in item["buyer"]
    assert "applicant" not in item

    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["seller_id"],
        "system_action": "refund_requested",
        "read_at": None,
    }) == 0

    reject_missing_reason = client.post(
        f"/api/v1/refunds/{refund_id}/seller-handle",
        headers=auth_headers(seller_token),
        json={"action": "refuse"},
    )
    assert reject_missing_reason.status_code == 422

    reject = client.post(
        f"/api/v1/refunds/{refund_id}/seller-handle",
        headers=auth_headers(seller_token),
        json={"action": "refuse", "reason": "商品已当面验收"},
    )
    assert reject.status_code == 200
    assert reject.get_json()["data"]["status_text"] == "已拒绝"

    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["buyer_id"],
        "system_action": "refund_seller_rejected",
        "read_at": None,
    }) == 1
    buyer_detail = client.get(f"/api/v1/refunds/{refund_id}", headers=auth_headers(buyer_token))
    assert buyer_detail.status_code == 200
    assert buyer_detail.get_json()["data"]["status_text"] == "已拒绝"
    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["buyer_id"],
        "system_action": "refund_seller_rejected",
        "read_at": None,
    }) == 0


def test_refund_agree_notifies_buyer_only():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品与描述不符", "refund_type": "refund_only"},
    )
    assert refund.status_code == 201
    refund_id = refund.get_json()["data"]["id"]
    refund_doc = app.db.refunds.find_one({"_id": ObjectId(refund_id)})

    agree = client.post(
        f"/api/v1/refunds/{refund_id}/seller-handle",
        headers=auth_headers(seller_token),
        json={"action": "agree", "reason": "卖家同意退款"},
    )
    assert agree.status_code == 200
    assert agree.get_json()["data"]["status_text"] == "已退款"
    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["buyer_id"],
        "system_action": "refund_seller_agreed",
        "read_at": None,
    }) == 1
    assert app.db.messages.count_documents({
        "refund_id": refund_doc["_id"],
        "receiver_id": refund_doc["seller_id"],
        "system_action": "refund_seller_agreed",
        "read_at": None,
    }) == 0


def test_seller_cancel_and_refund_creates_refund_and_refunds_payment():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)
    pay_order(client, buyer_token, order["id"])

    response = client.post(
        f"/api/v1/orders/{order['id']}/seller-cancel",
        headers=auth_headers(seller_token),
        json={"reason": "卖家临时无法交付"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "refunded"
    assert data["refund"]["status"] == "refunded"
    assert data["refund"]["reason"] == "卖家取消交易"
    assert data["payment"]["status"] == "refunded"
    assert data["escrow"]["status"] == "refunded"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["status"] == "off_shelf"

    order_object_id = ObjectId(order["id"])
    for action in ["seller_cancel_and_refund", "refund_success"]:
        assert app.db.business_logs.count_documents({"target_type": "order", "target_id": order_object_id, "action": action}) >= 1
    assert app.db.business_logs.count_documents({"target_type": "product", "target_id": ObjectId(product_id), "action": "product_off_shelf_after_refund"}) >= 1


def test_buyer_reject_creates_refund_record_and_order_detail_contains_refund():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)

    reject = client.post(
        f"/api/v1/deliveries/{order['id']}/buyer-reject",
        headers=auth_headers(buyer_token),
        json={"reason": "买家拒绝收货"},
    )
    assert reject.status_code == 200
    assert reject.get_json()["data"]["status"] == "refunding"

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert detail["status"] == "refunding"
    assert detail["refund"]["status"] == "requested"
    assert detail["refund"]["reason"] == "买家拒绝收货"
    assert detail["refund"]["amount"] == detail["pay_amount"]
    assert "view_refund" in detail["allowed_actions"]["actions"]
    assert "apply_appeal" not in detail["allowed_actions"]["actions"]

    order_object_id = ObjectId(order["id"])
    assert app.db.business_logs.count_documents({"target_type": "order", "target_id": order_object_id, "action": "buyer_reject_receive"}) >= 1
    assert app.db.business_logs.count_documents({"target_type": "order", "target_id": order_object_id, "action": "apply_refund"}) >= 1


def test_seller_reject_refund_then_appeal_admin_paths():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品问题", "refund_type": "refund_only"},
    )
    refund_id = refund.get_json()["data"]["id"]
    reject = client.post(
        f"/api/v1/refunds/{refund_id}/seller-reject",
        headers=auth_headers(seller_token),
        json={"reason": "卖家不同意"},
    )
    assert reject.status_code == 200
    assert reject.get_json()["data"]["status"] == "seller_rejected"

    appeal = client.post(
        "/api/v1/appeals",
        headers=auth_headers(buyer_token),
        json={"refund_id": refund_id, "reason": "申请平台介入"},
    )
    assert appeal.status_code == 201
    assert appeal.get_json()["data"]["status"] == "pending"

    arbitrate = client.post(
        f"/api/v1/admin/appeals/{appeal.get_json()['data']['id']}/arbitrate",
        headers=auth_headers(admin_token),
        json={"force_action": "reject_refund", "reason": "支持卖家"},
    )
    assert arbitrate.status_code == 200
    assert arbitrate.get_json()["data"]["status"] == "rejected"
    order_detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert order_detail["status"] == "pending_receive"


def test_appeal_evidence_images_are_saved_and_admin_list_returns_detail():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品问题", "refund_type": "refund_only", "evidence_images": ["/uploads/refund/r.png"]},
    )
    refund_id = refund.get_json()["data"]["id"]
    client.post(f"/api/v1/refunds/{refund_id}/seller-reject", headers=auth_headers(seller_token), json={"reason": "卖家不同意"})

    evidence = ["/uploads/appeal/a.png"]
    appeal = client.post(
        "/api/v1/appeals",
        headers=auth_headers(buyer_token),
        json={"refund_id": refund_id, "reason": "申请平台介入", "evidence_images": evidence},
    )
    assert appeal.status_code == 201
    assert appeal.get_json()["data"]["evidence_images"] == evidence

    list_response = client.get("/api/v1/admin/appeals?status=pending", headers=auth_headers(admin_token))
    assert list_response.status_code == 200
    items = list_response.get_json()["data"]["items"]
    first = next(item for item in items if item["id"] == appeal.get_json()["data"]["id"])
    assert first["refund"]["evidence_images"] == ["/uploads/refund/r.png"]
    assert first["payment"]["status"] == "paid"
    assert first["escrow"]["status"] == "holding"
    assert first["delivery"]["delivery_type"] == "offline_meetup"


def test_admin_arbitrate_refund_updates_appeal_status_approved():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    order = create_refundable_order(client, seller_token, buyer_token, admin_token)
    refund = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "amount": 20, "reason": "商品问题", "refund_type": "refund_only"},
    )
    refund_id = refund.get_json()["data"]["id"]
    client.post(f"/api/v1/refunds/{refund_id}/seller-reject", headers=auth_headers(seller_token), json={"reason": "卖家不同意"})
    appeal = client.post("/api/v1/appeals", headers=auth_headers(buyer_token), json={"refund_id": refund_id, "reason": "申请平台介入"})

    arbitrate = client.post(
        f"/api/v1/admin/appeals/{appeal.get_json()['data']['id']}/arbitrate",
        headers=auth_headers(admin_token),
        json={"force_action": "refund", "reason": "支持买家"},
    )
    assert arbitrate.status_code == 200
    assert arbitrate.get_json()["data"]["status"] == "approved"
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert detail["status"] == "refunded"
    assert detail["payment"]["status"] == "refunded"
