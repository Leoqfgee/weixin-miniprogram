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
      wx.showToast({ title: '最多上传 6 张凭证', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => this.uploadEvidence(res.tempFiles || [])
    })
  },
  uploadEvidence(files) {
    if (!files.length) return
    wx.showLoading({ title: '上传凭证' })
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'refund' },
      silentError: true
    }))).then((items) => {
      const urls = items.map((item) => item.url)
      this.setData({ evidenceImages: this.data.evidenceImages.concat(urls).slice(0, 6) })
      wx.showToast({ title: '凭证已上传', icon: 'success' })
    }).catch(() => {
      wx.showToast({ title: '图片上传失败，请稍后重试', icon: 'none' })
    }).finally(() => wx.hideLoading())
  },
  removeEvidence(event) {
    const index = event.currentTarget.dataset.index
    const images = this.data.evidenceImages.slice()
    images.splice(index, 1)
    this.setData({ evidenceImages: images })
  },
  validateForm() {
    const amount = Number(this.data.amount)
    if (!this.data.orderId) return '订单不存在，无法申请售后'
    if (!this.data.amount) return '退款金额不能为空'
    if (!Number.isFinite(amount) || amount <= 0) return '退款金额格式不正确'
    if (!this.data.reason.trim()) return '退款原因不能为空'
    return ''
  },
  submit() {
    const error = this.validateForm()
    if (error) {
      wx.showToast({ title: error, icon: 'none' })
      return
    }
    api.post('/refunds', {
      order_id: this.data.orderId,
      refund_type: this.data.refundTypes[this.data.refundTypeIndex].value,
      amount: Number(this.data.amount),
      reason: this.data.reason.trim(),
      description: this.data.description.trim(),
      evidence_images: this.data.evidenceImages
    }, { loading: true, loadingText: '提交售后' }).then((data) => {
      wx.showToast({ title: '已提交售后申请', icon: 'success' })
      const id = data.id
      if (id) {
        setTimeout(() => wx.redirectTo({ url: `/pages/refund/detail/index?id=${id}` }), 500)
      } else {
        setTimeout(() => wx.navigateBack(), 500)
      }
    })
  }
})
