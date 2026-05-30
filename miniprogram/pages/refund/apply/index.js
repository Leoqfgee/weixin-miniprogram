const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    orderId: '',
    amount: '',
    reason: '',
    description: '',
    refundTypes: [
      { label: '仅退款', value: 'refund_only' },
      { label: '退货退款', value: 'return_and_refund' }
    ],
    refundTypeIndex: 0
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
  onDescriptionInput(event) {
    this.setData({ description: event.detail.value })
  },
  onRefundTypeChange(event) {
    this.setData({ refundTypeIndex: Number(event.detail.value) })
  },
  submit() {
    api.post('/refunds', {
      order_id: this.data.orderId,
      refund_type: this.data.refundTypes[this.data.refundTypeIndex].value,
      amount: Number(this.data.amount),
      reason: this.data.reason,
      description: this.data.description,
      evidence_images: []
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已申请退款', icon: 'success' })
      wx.navigateBack()
    })
  }
})
