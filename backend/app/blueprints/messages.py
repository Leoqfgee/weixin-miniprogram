from flask import Blueprint, current_app, g, request

from ..services.engagement import MessageService
from ..utils.jwt import auth_required
from ..utils.response import success_response

messages_bp = Blueprint("messages", __name__)


@messages_bp.post("/messages")
@auth_required
def send_message():
    data = MessageService(current_app.db).send_message(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@messages_bp.get("/messages/conversations")
@auth_required
def list_conversations():
    data = MessageService(current_app.db).list_conversations(g.current_user_id)
    return success_response(data)


@messages_bp.get("/messages/support")
@auth_required
def get_support_contact():
    data = MessageService(current_app.db).get_support_contact(g.current_user_id)
    return success_response(data)


@messages_bp.get("/messages/conversations/<conversation_id>")
@auth_required
def list_messages(conversation_id):
    data = MessageService(current_app.db).list_messages(g.current_user_id, conversation_id)
    return success_response(data)


@messages_bp.get("/messages/<conversation_id>")
@auth_required
def list_messages_alias(conversation_id):
    data = MessageService(current_app.db).list_messages(g.current_user_id, conversation_id)
    return success_response(data)


@messages_bp.get("/notifications")
@auth_required
def list_notifications():
    data = MessageService(current_app.db).list_notifications(g.current_user_id)
    return success_response(data)
