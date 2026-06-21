from flask import Blueprint, current_app, g, request

from ..services.engagement import AdminReportService, AppealService, RefundService
from ..services.products import ProductService
from ..services.credit import CreditService
from ..services.reports import ReportService
from ..utils.jwt import roles_required
from ..utils.response import success_response

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/admin/products")
@roles_required("admin")
def list_admin_products():
    data = ProductService(current_app.db).list_admin_products(request.args, g.current_user)
    return success_response(data)


@admin_bp.post("/admin/products/<product_id>/audit")
@roles_required("admin")
def audit_product(product_id):
    payload = request.get_json(silent=True) or {}
    data = ProductService(current_app.db).audit_product(
        product_id,
        g.current_user,
        payload,
        trace_id=getattr(g, "trace_id", None),
    )
    return success_response(data)


@admin_bp.get("/admin/reports")
@roles_required("admin")
def list_violation_reports():
    data = ReportService(current_app.db).list_admin_reports(request.args)
    return success_response(data)


@admin_bp.get("/admin/reports/<report_id>")
@roles_required("admin")
def get_violation_report(report_id):
    data = ReportService(current_app.db).get_admin_report(report_id)
    return success_response(data)


@admin_bp.post("/admin/reports/<report_id>/handle")
@roles_required("admin")
def handle_violation_report(report_id):
    data = ReportService(current_app.db).handle_report(report_id, g.current_user, request.get_json(silent=True) or {})
    return success_response(data)


@admin_bp.post("/admin/users/<user_id>/credit/adjust")
@roles_required("admin")
def admin_adjust_credit(user_id):
    data = CreditService(current_app.db).admin_adjust(user_id, request.get_json(silent=True) or {}, g.current_user)
    return success_response(data)


@admin_bp.post("/admin/refunds/<refund_id>/arbitrate")
@roles_required("admin")
def arbitrate_refund(refund_id):
    data = RefundService(current_app.db).admin_arbitrate(
        refund_id,
        g.current_user,
        request.get_json(silent=True) or {},
        trace_id=getattr(g, "trace_id", None),
    )
    return success_response(data)


@admin_bp.post("/admin/appeals/<appeal_id>/arbitrate")
@roles_required("admin")
def arbitrate_appeal(appeal_id):
    data = AppealService(current_app.db).arbitrate(
        appeal_id,
        g.current_user,
        request.get_json(silent=True) or {},
    )
    return success_response(data)


@admin_bp.get("/admin/appeals")
@roles_required("admin")
def list_admin_appeals():
    data = AppealService(current_app.db).list_appeals(g.current_user, request.args)
    return success_response(data)


@admin_bp.get("/admin/refunds")
@roles_required("admin")
def list_admin_refunds():
    data = RefundService(current_app.db).list_refunds(g.current_user, request.args)
    return success_response(data)


@admin_bp.get("/admin/operation-logs")
@roles_required("admin")
def list_operation_logs():
    data = AdminReportService(current_app.db).list_operation_logs(request.args)
    return success_response(data)


@admin_bp.get("/admin/stats")
@roles_required("admin")
def get_stats():
    data = AdminReportService(current_app.db).stats()
    return success_response(data)


@admin_bp.get("/admin/reports/summary")
@roles_required("admin")
def report_summary():
    data = AdminReportService(current_app.db).summary(request.args)
    return success_response(data)


@admin_bp.get("/admin/reports/products")
@roles_required("admin")
def report_products():
    data = AdminReportService(current_app.db).products(request.args)
    return success_response(data)


@admin_bp.get("/admin/reports/orders")
@roles_required("admin")
def report_orders():
    data = AdminReportService(current_app.db).orders(request.args)
    return success_response(data)


@admin_bp.get("/admin/reports/categories")
@roles_required("admin")
def report_categories():
    data = AdminReportService(current_app.db).categories(request.args)
    return success_response(data)


@admin_bp.get("/admin/reports/users")
@roles_required("admin")
def report_users():
    data = AdminReportService(current_app.db).users(request.args)
    return success_response(data)
