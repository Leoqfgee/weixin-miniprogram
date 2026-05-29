const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    orderId: '',
    amount: '',
    reason: ''
  },
  onLoad(options) {
    requireLogin()
    this.setData({ orderId: options.order_id || '', amount: options.amount || '' })
  },
  onAmountInput(event) {
    this.setData({ amount: event.detail.value })
  },
  onReasonInput(event) {
    this.setData({ reason: event.detail.value })
  },
  submit() {
    api.post('/refunds', {
      order_id: this.data.orderId,
      amount: Number(this.data.amount),
      reason: this.data.reason,
      evidence_images: []
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已申请退款', icon: 'success' })
      wx.navigateBack()
    })
  }
})
