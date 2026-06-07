from flask import Blueprint, current_app, g, request

from ..services.users import AddressService
from ..utils.jwt import auth_required
from ..utils.response import success_response

addresses_bp = Blueprint("addresses", __name__)


@addresses_bp.get("/addresses")
@auth_required
def list_addresses():
    return success_response(AddressService(current_app.db).list_addresses(g.current_user_id))


@addresses_bp.post("/addresses")
@auth_required
def create_address():
    data = AddressService(current_app.db).create_address(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@addresses_bp.put("/addresses/<address_id>")
@auth_required
def update_address(address_id):
    data = AddressService(current_app.db).update_address(
        g.current_user_id, address_id, request.get_json(silent=True) or {}
    )
    return success_response(data)


@addresses_bp.delete("/addresses/<address_id>")
@auth_required
def delete_address(address_id):
    data = AddressService(current_app.db).delete_address(g.current_user_id, address_id)
    return success_response(data)


@addresses_bp.post("/addresses/<address_id>/default")
@auth_required
def set_default_address(address_id):
    data = AddressService(current_app.db).set_default(g.current_user_id, address_id)
    return success_response(data)
