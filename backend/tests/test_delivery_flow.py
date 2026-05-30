from test_phase3_trade_flow import auth_headers, create_on_sale_product, create_order, pay_order, setup_flow


def test_seller_deliver_and_buyer_confirm_receive_settle_escrow():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)
    pay_order(client, buyer_token, order["id"])

    forbidden = client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(buyer_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口"},
    )
    assert forbidden.status_code == 403

    deliver = client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(seller_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口"},
    )
    assert deliver.status_code == 200
    assert deliver.get_json()["data"]["order"]["status"] == "pending_receive"

    receive = client.post(f"/api/v1/deliveries/{order['id']}/buyer-confirm", headers=auth_headers(buyer_token))
    assert receive.status_code == 200
    assert receive.get_json()["data"]["order"]["status"] == "pending_review"
    assert receive.get_json()["data"]["escrow"]["status"] == "settled"
