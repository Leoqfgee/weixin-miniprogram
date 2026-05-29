import uuid

from flask import g, request


def register_trace_hooks(app):
    @app.before_request
    def attach_trace_id():
        # 优先沿用调用方传入的 trace，便于小程序和后端日志串联。
        g.trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex

    @app.after_request
    def expose_trace_id(response):
        response.headers["X-Trace-Id"] = getattr(g, "trace_id", "")
        return response
