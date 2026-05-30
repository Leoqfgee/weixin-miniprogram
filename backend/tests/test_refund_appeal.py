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
