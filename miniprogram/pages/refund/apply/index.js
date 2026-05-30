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
    refundTypeIndex: 0,
    evidenceImages: []
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
  chooseEvidence() {
    const remain = 6 - this.data.evidenceImages.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传 6 张', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      success: (res) => this.uploadEvidence(res.tempFiles || [])
    })
  },
  uploadEvidence(files) {
    if (!files.length) return
    wx.showLoading({ title: '上传凭证' })
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'refund' }
    }))).then((items) => {
      const urls = items.map((item) => item.url)
      this.setData({ evidenceImages: this.data.evidenceImages.concat(urls).slice(0, 6) })
      wx.showToast({ title: '凭证已上传', icon: 'success' })
    }).finally(() => wx.hideLoading())
  },
  removeEvidence(event) {
    const index = event.currentTarget.dataset.index
    const images = this.data.evidenceImages.slice()
    images.splice(index, 1)
    this.setData({ evidenceImages: images })
  },
  submit() {
    api.post('/refunds', {
      order_id: this.data.orderId,
      refund_type: this.data.refundTypes[this.data.refundTypeIndex].value,
      amount: Number(this.data.amount),
      reason: this.data.reason,
      description: this.data.description,
      evidence_images: this.data.evidenceImages
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已申请退款', icon: 'success' })
      wx.navigateBack()
    })
  }
})
