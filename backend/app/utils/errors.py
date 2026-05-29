from werkzeug.exceptions import HTTPException

from .response import error_response


class AppError(Exception):
    """业务异常基类，统一映射为标准失败响应。"""

    def __init__(self, code, message, http_status=400, errors=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.errors = errors or []


class UnauthorizedError(AppError):
    def __init__(self, message="请先登录", errors=None):
        super().__init__(40100, message, 401, errors)


class ForbiddenError(AppError):
    def __init__(self, message="无权限执行该操作", errors=None):
        super().__init__(40300, message, 403, errors)


class NotFoundError(AppError):
    def __init__(self, message="资源不存在", errors=None):
        super().__init__(40400, message, 404, errors)


class ConflictError(AppError):
    def __init__(self, message="当前状态不允许该操作", errors=None):
        super().__init__(40900, message, 409, errors)


class ValidationError(AppError):
    def __init__(self, message="参数校验失败", errors=None):
        super().__init__(42200, message, 422, errors)


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(exc):
        return error_response(exc.code, exc.message, exc.errors, exc.http_status)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return error_response(
            exc.code * 100,
            exc.description or exc.name,
            [],
            exc.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        app.logger.exception("unexpected_error")
        return error_response(50000, "服务器内部错误", [], 500)
