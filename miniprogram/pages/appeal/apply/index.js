const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    refundId: '',
    reason: '',
    description: '',
    evidenceImages: []
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
      formData: { usage: 'appeal' }
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
    api.post('/appeals', {
      refund_id: this.data.refundId,
      reason: this.data.reason,
      description: this.data.description,
      evidence_images: this.data.evidenceImages
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已申请平台介入', icon: 'success' })
      wx.navigateBack()
    })
  }
})
