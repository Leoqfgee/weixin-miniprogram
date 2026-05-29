from abc import ABC, abstractmethod


class PaymentAdapter(ABC):
    @abstractmethod
    def create_payment(self, order, amount):
        raise NotImplementedError

    @abstractmethod
    def confirm_payment(self, payment, payload):
        raise NotImplementedError


class MockPaymentAdapter(PaymentAdapter):
    def create_payment(self, order, amount):
        return {"channel": "mock", "amount": amount}

    def confirm_payment(self, payment, payload):
        mock_result = payload.get("mock_result", "success")
        return {"success": mock_result == "success", "raw": {"mock_result": mock_result}}


class WechatPayAdapter(PaymentAdapter):
    def create_payment(self, order, amount):
        # 真实微信支付接入时在这里统一封装下单、签名和 prepay_id。
        return {"channel": "wechat", "amount": amount}

    def confirm_payment(self, payment, payload):
        # 真实微信支付回调应在这里做验签、金额校验和幂等处理。
        raise NotImplementedError("微信支付适配器尚未接入真实商户配置")


def get_payment_adapter(mode="mock"):
    if mode == "wechat":
        return WechatPayAdapter()
    return MockPaymentAdapter()
