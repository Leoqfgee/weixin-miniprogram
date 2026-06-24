const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    application: null,
    statusText: '未认证',
    cardImage: '',
    school: '',
    studentNo: '',
    realName: '',
    submitting: false
  },
  onLoad() {
    if (!requireLogin()) return
    this.loadApplication()
  },
  onShow() {
    if (requireLogin()) this.loadApplication()
  },
  loadApplication() {
    api.get('/student-verifications/me').then((data) => {
      this.setData({
        application: data.application,
        statusText: data.status_text || '未认证'
      })
    })
  },
  chooseCardImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = (res.tempFiles || [])[0]
        if (file && file.tempFilePath) this.setData({ cardImage: file.tempFilePath })
      }
    })
  },
  onInput(event) {
    this.setData({ [event.currentTarget.dataset.field]: event.detail.value })
  },
  submitApplication() {
    if (this.data.submitting) return
    if (!this.data.cardImage) {
      wx.showToast({ title: '请上传学生证照片', icon: 'none' })
      return
    }
    if (!this.data.school.trim() || !this.data.realName.trim()) {
      wx.showToast({ title: '请填写学校和姓名', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    api.uploadFile({
      url: '/files/upload',
      filePath: this.data.cardImage,
      formData: { usage: 'student_verification' },
      loading: true
    }).then((file) => api.post('/student-verifications', {
      school: this.data.school,
      real_name: this.data.realName,
      student_no: this.data.studentNo,
      card_image_url: file.url,
      student_card_images: [file.url]
    }, { loading: true })).then((application) => {
      wx.showToast({ title: '提交成功', icon: 'success' })
      this.setData({
        application,
        statusText: application.status_text || '认证审核中',
        cardImage: '',
        school: '',
        studentNo: '',
        realName: ''
      })
    }).catch((err) => {
      wx.showToast({ title: err.message || '提交失败', icon: 'none' })
    }).finally(() => {
      this.setData({ submitting: false })
    })
  },
  reApply() {
    this.setData({ application: null, statusText: '未认证' })
  },
  previewCard() {
    const url = this.data.cardImage || (this.data.application && this.data.application.card_image_url)
    if (url) wx.previewImage({ urls: [url], current: url })
  }
})
