const api = require('../../../utils/request')
const { requireLogin, getUser } = require('../../../utils/auth')

const reasons = [
  { label: '辱骂骚扰 / 不当言论', value: 'harassment' },
  { label: '欺诈风险', value: 'fraud' },
  { label: '发布违规商品', value: 'illegal_product' },
  { label: '恶意交易 / 恶意退款', value: 'malicious_trade' },
  { label: '冒充他人 / 虚假身份', value: 'fake_identity' },
  { label: '其他', value: 'other' }
]

Page({
  data: {
    userId: '',
    user: null,
    reasons,
    reasonType: '',
    description: '',
    evidenceImages: []
  },
  onLoad(options) {
    if (!requireLogin()) return
    const userId = options.user_id || options.id || ''
    const current = getUser() || {}
    if (userId && userId === current.id) {
      wx.showToast({ title: '不能举报自己', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 600)
      return
    }
    this.setData({ userId })
    this.loadUser()
  },
  loadUser() {
    if (!this.data.userId) return
    api.get(`/users/${this.data.userId}/profile`).then((data) => {
      this.setData({
        user: {
          nickname: data.user.nickname,
          avatar: data.user.avatar || data.user.avatar_url
        }
      })
    })
  },
  chooseReason(event) {
    this.setData({ reasonType: event.currentTarget.dataset.value })
  },
  onDescription(event) {
    this.setData({ description: event.detail.value.slice(0, 200) })
  },
  chooseEvidence() {
    wx.chooseMedia({
      count: 3 - this.data.evidenceImages.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => this.uploadEvidence(res.tempFiles || [])
    })
  },
  uploadEvidence(files) {
    if (!files.length) return
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'report' },
      loading: true
    }))).then((items) => {
      this.setData({ evidenceImages: this.data.evidenceImages.concat(items.map((item) => item.url)).slice(0, 3) })
    })
  },
  removeEvidence(event) {
    const evidenceImages = this.data.evidenceImages.slice()
    evidenceImages.splice(Number(event.currentTarget.dataset.index), 1)
    this.setData({ evidenceImages })
  },
  submitReport() {
    if (!this.data.reasonType) {
      wx.showToast({ title: '请选择举报原因', icon: 'none' })
      return
    }
    api.post('/reports', {
      target_type: 'user',
      target_user_id: this.data.userId,
      reason_type: this.data.reasonType,
      description: this.data.description,
      evidence_images: this.data.evidenceImages
    }, { loading: true }).then(() => {
      wx.showToast({ title: '举报已提交，平台会尽快处理', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 800)
    })
  }
})
