const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    refundId: '',
    reason: '',
    description: ''
  },
  onLoad(options) {
    requireLogin()
    this.setData({ refundId: options.refund_id || '' })
  },
  onReasonInput(event) {
    this.setData({ reason: event.detail.value })
  },
  onDescriptionInput(event) {
    this.setData({ description: event.detail.value })
  },
  submit() {
    api.post('/appeals', {
      refund_id: this.data.refundId,
      reason: this.data.reason,
      description: this.data.description,
      evidence_images: []
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已申请平台介入', icon: 'success' })
      wx.navigateBack()
    })
  }
})
