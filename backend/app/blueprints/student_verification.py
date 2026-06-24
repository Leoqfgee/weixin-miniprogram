from flask import Blueprint, current_app, g, request

from ..services.student_verification import StudentVerificationService
from ..utils.jwt import auth_required, roles_required
from ..utils.response import success_response


student_verification_bp = Blueprint("student_verification", __name__)


# 用户端接口
@student_verification_bp.post("/student-verifications")
@auth_required
def create_application():
    """提交学生认证申请"""
    data = StudentVerificationService(current_app.db).create_application(
        g.current_user_id,
        request.get_json(silent=True) or {}
    )
    return success_response(data)


@student_verification_bp.get("/student-verifications/me")
@auth_required
def get_my_application():
    """获取我的认证申请"""
    data = StudentVerificationService(current_app.db).get_my_application(g.current_user_id)
    return success_response(data)


@student_verification_bp.get("/users/<user_id>/verification-status")
@auth_required
def get_user_verification_status(user_id):
    """获取指定用户的认证状态"""
    data = StudentVerificationService(current_app.db).get_verification_status(user_id)
    return success_response(data)


# 管理员接口
@student_verification_bp.get("/admin/student-verifications")
@roles_required("admin")
def list_admin_applications():
    """管理员获取认证申请列表"""
    data = StudentVerificationService(current_app.db).list_admin_applications(request.args)
    return success_response(data)


@student_verification_bp.get("/admin/student-verifications/<application_id>")
@roles_required("admin")
def get_admin_application(application_id):
    """管理员获取认证申请详情"""
    data = StudentVerificationService(current_app.db).get_admin_application(application_id)
    return success_response(data)


@student_verification_bp.post("/admin/student-verifications/<application_id>/review")
@roles_required("admin")
def review_application(application_id):
    """管理员审核认证申请"""
    data = StudentVerificationService(current_app.db).review_application(
        application_id,
        g.current_user,
        request.get_json(silent=True) or {}
    )
    return success_response(data)