from bson import ObjectId

from ..repositories.carts import CartRepository
from ..repositories.products import ProductRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.serializers import serialize_doc, to_object_id


class CartService:
    def __init__(self, db):
        self.carts = CartRepository(db)
        self.products = ProductRepository(db)

    def add_item(self, user_id, payload):
        product_id = to_object_id(payload.get("product_id"), "product_id")
        quantity = _validate_quantity(payload.get("quantity", 1))
        product = self._get_buyable_product(product_id, user_id)
        if product.get("stock", 0) < quantity:
            raise ConflictError("商品库存不足")

        cart = self.carts.get_by_user(ObjectId(str(user_id))) or {"items": []}
        items = cart.get("items", [])
        changed = False
        for item in items:
            if item.get("product_id") == product["_id"]:
                item["quantity"] = quantity
                changed = True
                break
        if not changed:
            items.append({"product_id": product["_id"], "quantity": quantity})
        self.carts.save_items(ObjectId(str(user_id)), items)
        return self.get_cart(user_id)

    def get_cart(self, user_id):
        cart = self.carts.get_by_user(ObjectId(str(user_id))) or {"items": []}
        items = []
        for item in cart.get("items", []):
            product = self.products.find_by_id(item["product_id"])
            if not product:
                valid = False
                product_data = None
                reason = "商品不存在"
            else:
                valid = product.get("status") == "on_sale" and product.get("stock", 0) >= item["quantity"]
                product_data = _cart_product(product)
                reason = "" if valid else "商品已下架或库存不足"
            items.append(
                {
                    "product_id": str(item["product_id"]),
                    "quantity": item["quantity"],
                    "valid": valid,
                    "invalid_reason": reason,
                    "product": product_data,
                }
            )
        return {"items": items}

    def update_item(self, user_id, product_id, payload):
        object_id = to_object_id(product_id, "product_id")
        quantity = _validate_quantity(payload.get("quantity"))
        product = self._get_buyable_product(object_id, user_id)
        if product.get("stock", 0) < quantity:
            raise ConflictError("商品库存不足")
        cart = self.carts.get_by_user(ObjectId(str(user_id)))
        if not cart:
            raise NotFoundError("购物车中没有该商品")
        items = cart.get("items", [])
        found = False
        for item in items:
            if item.get("product_id") == object_id:
                item["quantity"] = quantity
                found = True
                break
        if not found:
            raise NotFoundError("购物车中没有该商品")
        self.carts.save_items(ObjectId(str(user_id)), items)
        return self.get_cart(user_id)

    def delete_item(self, user_id, product_id):
        object_id = to_object_id(product_id, "product_id")
        cart = self.carts.get_by_user(ObjectId(str(user_id)))
        if not cart:
            return self.get_cart(user_id)
        items = [item for item in cart.get("items", []) if item.get("product_id") != object_id]
        self.carts.save_items(ObjectId(str(user_id)), items)
        return self.get_cart(user_id)

    def _get_buyable_product(self, product_id, user_id):
        product = self.products.find_by_id(product_id)
        if not product:
            raise NotFoundError("商品不存在")
        if product.get("status") != "on_sale":
            raise ConflictError("商品当前不可购买")
        if str(product.get("seller_id")) == str(user_id):
            raise ForbiddenError("不能购买自己的商品")
        return product


def _validate_quantity(value):
    if not isinstance(value, int) or value <= 0:
        raise ValidationError("参数校验失败", [{"field": "quantity", "message": "数量必须是正整数"}])
    return value


def _cart_product(product):
    data = serialize_doc(product)
    return {
        "id": data["id"],
        "title": data.get("title"),
        "price": data.get("price"),
        "cover_image": data.get("cover_image"),
        "stock": data.get("stock"),
        "status": data.get("status"),
    }
