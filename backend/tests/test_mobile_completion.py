from bson import ObjectId

from test_phase3_trade_flow import (
    auth_headers,
    create_on_sale_product,
    pay_order,
    setup_flow,
)


def test_address_default_switch_and_express_order_snapshot():
    app, client, seller_token, buyer_token, admin_token = setup_flow()

    first = client.post(
        "/api/v1/addresses",
        headers=auth_headers(buyer_token),
        json={"name": "Alice", "phone": "13800000000", "address": "Dorm 1"},
    )
    assert first.status_code == 201
    assert first.get_json()["data"]["is_default"] is True

    second = client.post(
        "/api/v1/addresses",
        headers=auth_headers(buyer_token),
        json={"name": "Alice", "phone": "13800000000", "address": "Dorm 2", "is_default": True},
    )
    assert second.status_code == 201
    second_address = second.get_json()["data"]

    addresses = client.get("/api/v1/addresses", headers=auth_headers(buyer_token)).get_json()["data"]["items"]
    assert len(addresses) >= 2
    assert sum(1 for item in addresses if item["is_default"]) == 1
    assert addresses[0]["id"] == second_address["id"]

    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, "express-mobile-completion"),
        json={
            "product_id": product_id,
            "quantity": 1,
            "delivery_type": "express",
            "shipping_address_id": second_address["id"],
        },
    )
    assert order_response.status_code == 201
    order = order_response.get_json()["data"]
    assert order["shipping_address"]["address"] == "Dorm 2"

    client.put(
        f"/api/v1/addresses/{second_address['id']}",
        headers=auth_headers(buyer_token),
        json={"name": "Alice", "phone": "13800000000", "address": "Dorm changed"},
    )
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert detail["shipping_address"]["address"] == "Dorm 2"


def test_deleted_address_cannot_be_reused_from_stale_order_page():
    app, client, seller_token, buyer_token, admin_token = setup_flow()

    address_response = client.post(
        "/api/v1/addresses",
        headers=auth_headers(buyer_token),
        json={"name": "Alice", "phone": "13800000000", "address": "Dorm stale"},
    )
    assert address_response.status_code == 201
    stale_address = address_response.get_json()["data"]
    delete_response = client.delete(
        f"/api/v1/addresses/{stale_address['id']}",
        headers=auth_headers(buyer_token),
    )
    assert delete_response.status_code == 200

    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, "stale-deleted-address"),
        json={
            "product_id": product_id,
            "quantity": 1,
            "delivery_type": "express",
            "shipping_address_id": stale_address["id"],
            "shipping_address": stale_address,
        },
    )
    assert order_response.status_code == 404
    assert "收货地址不存在或已删除" in str(order_response.get_json())


def test_incomplete_draft_edit_and_mutual_anonymous_reviews_in_chat():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]

    draft = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={"description": "finish later", "submit_action": "draft"},
    )
    assert draft.status_code == 201
    product_id = draft.get_json()["data"]["id"]

    edit = client.put(
        f"/api/v1/products/{product_id}",
        headers=auth_headers(seller_token),
        json={"title": "Edited draft", "price": 22, "category_id": category_id, "condition": "", "campus": "东校区"},
    )
    assert edit.status_code == 200
    submit = client.post(f"/api/v1/products/{product_id}/submit-review", headers=auth_headers(seller_token))
    assert submit.status_code == 200
    assert submit.get_json()["data"]["status"] == "on_sale"
    order = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, "mutual-review-mobile-completion"),
        json={"product_id": product_id, "quantity": 1, "delivery_type": "offline_meetup", "meet_location": "Library"},
    ).get_json()["data"]
    pay_order(client, buyer_token, order["id"])
    client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(seller_token),
        json={"delivery_type": "offline_meetup", "meet_location": "Library"},
    )
    client.post(f"/api/v1/deliveries/{order['id']}/buyer-confirm", headers=auth_headers(buyer_token))

    buyer_review = client.post(
        "/api/v1/reviews",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "rating": 5, "content": "Great seller"},
    )
    assert buyer_review.status_code == 201
    seller_review = client.post(
        "/api/v1/reviews",
        headers=auth_headers(seller_token),
        json={"order_id": order["id"], "rating": 4, "content": "Smooth trade", "anonymous": True},
    )
    assert seller_review.status_code == 201
    assert seller_review.get_json()["data"]["reviewer"]["nickname"] != "Seller Demo"

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token)).get_json()["data"]
    assert detail["status"] == "completed"
    assert len(detail["reviews"]) == 2
    assert detail["current_role"] == "buyer"
    assert detail["contact_label"] == "联系卖家"
    assert detail["conversation_id"]
    assert detail["status_text"] == "交易完成"

    conversation = client.get("/api/v1/messages/conversations", headers=auth_headers(buyer_token)).get_json()["data"]["items"][0]
    assert conversation["order_id"] == order["id"]
    assert conversation["product"]["title"]
    messages = client.get(
        f"/api/v1/messages/{conversation['conversation_id']}",
        headers=auth_headers(buyer_token),
    ).get_json()["data"]["items"]
    assert any(item["message_type"] == "review" and item["review_id"] for item in messages)
    assert any(item["message_type"] == "system" for item in messages)

    buyer_id = app.db.users.find_one({"phone": "18800000002"})["_id"]
    public_profile = client.get(f"/api/v1/users/{buyer_id}/profile").get_json()["data"]
    assert public_profile["user"]["review_count"] >= 1
    assert public_profile["reviews"]

    me = client.get("/api/v1/users/me", headers=auth_headers(buyer_token)).get_json()["data"]
    assert me["stats"]["bought"] >= 1
    assert me["stats"]["published"] == 0
    assert me["stats"]["favorites"] == 0


def test_on_sale_edit_republish_delete_and_admin_support_contact():
    app, client, seller_token, buyer_token, admin_token = setup_flow()

    editable_id = create_on_sale_product(client, seller_token, admin_token, stock=2, price=30)
    editable = client.get(f"/api/v1/products/{editable_id}", headers=auth_headers(seller_token)).get_json()["data"]
    assert editable["allowed_actions"]["can_edit"] is True
    assert editable["allowed_actions"]["can_submit_review"] is False

    edited = client.put(
        f"/api/v1/products/{editable_id}",
        headers=auth_headers(seller_token),
        json={"price": 28},
    )
    assert edited.status_code == 200
    assert edited.get_json()["data"]["price"] == 28
    assert edited.get_json()["data"]["status"] == "on_sale"

    client.post(f"/api/v1/products/{editable_id}/off-shelf", headers=auth_headers(seller_token), json={})
    off_shelf = client.get(f"/api/v1/products/{editable_id}", headers=auth_headers(seller_token)).get_json()["data"]
    assert off_shelf["allowed_actions"]["can_edit"] is True
    assert off_shelf["allowed_actions"]["can_submit_review"] is False
    assert off_shelf["allowed_actions"]["can_republish"] is True
    assert off_shelf["allowed_actions"]["can_delete"] is True

    republished = client.post(f"/api/v1/products/{editable_id}/republish", headers=auth_headers(seller_token))
    assert republished.status_code == 200
    assert republished.get_json()["data"]["status"] == "on_sale"

    deletable_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    client.post(f"/api/v1/products/{deletable_id}/off-shelf", headers=auth_headers(seller_token), json={})
    deleted = client.delete(f"/api/v1/products/{deletable_id}", headers=auth_headers(seller_token))
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/products/{deletable_id}", headers=auth_headers(seller_token)).status_code == 404
    mine = client.get("/api/v1/products/mine?status=off_shelf", headers=auth_headers(seller_token)).get_json()["data"]["items"]
    assert all(item["id"] != deletable_id for item in mine)

    support = client.get("/api/v1/messages/support", headers=auth_headers(buyer_token))
    assert support.status_code == 200
    assert support.get_json()["data"]["nickname"] == "平台客服"
    admin_id = app.db.users.find_one({"phone": "18800000000"})["_id"]
    assert support.get_json()["data"]["id"] == str(admin_id)
