from urllib.parse import urlencode
from urllib.request import urlopen
import json

from flask import current_app

from ..utils.errors import UnauthorizedError, ValidationError


class WechatAuthAdapter:
    """Encapsulates WeChat code2Session login."""

    def code_to_session(self, code):
        mode = current_app.config.get("WECHAT_AUTH_MODE", "mock").strip()
        if mode == "mock":
            return {
                "openid": f"local_wechat_{code}",
                "session_key": "mock_session_key",
                "unionid": None,
            }
        if not code:
            raise ValidationError("参数校验失败", [{"field": "code", "message": "微信登录 code 不能为空"}])

        appid = current_app.config.get("WECHAT_APPID", "").strip()
        secret = current_app.config.get("WECHAT_SECRET", "").strip()
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
