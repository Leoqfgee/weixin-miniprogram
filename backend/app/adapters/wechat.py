from urllib.parse import urlencode
from urllib.request import urlopen
import json

from flask import current_app

from ..utils.errors import UnauthorizedError, ValidationError


class WechatAuthAdapter:
    """封装微信登录能力；课程本地开发默认走 mock，部署时可切换真实 code2Session。"""

    def code_to_session(self, code, mock_openid=None):
        mode = current_app.config.get("WECHAT_AUTH_MODE", "mock")
        if mode == "mock":
            # 本地演示没有微信 appsecret，允许前端传稳定 mock_openid，避免每次 code 变化产生新账号。
            return {
                "openid": mock_openid or f"mock_wechat_{code}",
                "session_key": "mock_session_key",
                "unionid": None,
            }
        if not code:
            raise ValidationError("参数校验失败", [{"field": "code", "message": "微信登录 code 不能为空"}])

        appid = current_app.config.get("WECHAT_APPID")
        secret = current_app.config.get("WECHAT_APPSECRET")
        if not appid or not secret:
            raise UnauthorizedError("微信登录配置缺失")

        query = urlencode(
            {
                "appid": appid,
                "secret": secret,
                "js_code": code,
                "grant_type": "authorization_code",
            }
        )
        with urlopen(f"https://api.weixin.qq.com/sns/jscode2session?{query}", timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("errcode"):
            raise UnauthorizedError(f"微信登录失败：{data.get('errmsg', 'code2Session error')}")
        return data
