from bson import ObjectId

from test_phase3_trade_flow import auth_headers, create_on_sale_product, create_order, pay_order, setup_flow


def test_payment_success_creates_single_holding_escrow():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)

    result = pay_order(client, buyer_token, order["id"])
    assert result["order_status"] == "pending_delivery"
    assert result["payment"]["status"] == "paid"
    assert result["escrow"]["status"] == "holding"

    response = client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "mock_result": "success"},
    )
    assert response.status_code == 200
    assert app.db.payments.count_documents({"order_id": ObjectId(order["id"])}) == 1
    assert app.db.escrow_records.count_documents({"order_id": ObjectId(order["id"])}) == 1
