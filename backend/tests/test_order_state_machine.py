from bson import ObjectId

from test_phase3_trade_flow import create_on_sale_product, create_order, setup_flow


def test_order_create_locks_product_and_buyer_cancel_reopens():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)

    assert order["status"] == "pending_payment"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["status"] == "locked"

    response = client.post(
        f"/api/v1/orders/{order['id']}/buyer-cancel",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "closed"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["status"] == "on_sale"
