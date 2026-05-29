const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    id: '',
    order: null
  },
  onLoad(options) {
    requireLogin()
    this.setData({ id: options.id || '' })
    this.loadOrder()
  },
  loadOrder() {
    if (!this.data.id) return
    api.get(`/orders/${this.data.id}`, {}, { loading: true }).then((data) => {
      this.setData({ order: data })
    })
  },
  pay() {
    api.post('/payments/mock-confirm', {
      payment_id: this.data.order.payment.id,
      mock_result: 'success'
    }, { loading: true }).then(() => {
      wx.showToast({ title: '支付成功', icon: 'success' })
      this.loadOrder()
    })
  },
  cancel() {
    api.post(`/orders/${this.data.id}/cancel`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已取消', icon: 'success' })
      this.loadOrder()
    })
  },
  confirmReceipt() {
    api.post(`/deliveries/${this.data.id}/confirm`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已确认收货', icon: 'success' })
      this.loadOrder()
    })
  },
  review() {
    wx.showModal({
      title: '订单评价',
      editable: true,
      placeholderText: '写一句评价',
      success: (res) => {
        if (!res.confirm) return
        api.post('/reviews', {
          order_id: this.data.id,
          rating: 5,
          content: res.content || '交易顺利'
        }, { loading: true }).then(() => {
          wx.showToast({ title: '评价成功', icon: 'success' })
          this.loadOrder()
        })
      }
    })
  },
  applyRefund() {
    wx.navigateTo({ url: `/pages/refund/apply/index?order_id=${this.data.id}&amount=${this.data.order.pay_amount}` })
  }
})
