const api = require('../../../utils/request')
const { getToken, getUser, requireLogin, saveAuth } = require('../../../utils/auth')

Page({
  data: {
    form: {
      avatar: '',
      nickname: '',
      campus: '',
      bio: ''
    }
  },
  onShow() {
    if (!requireLogin()) return
    const user = getUser()
    const profile = (user && user.profile) || {}
    this.setData({
      form: {
        avatar: profile.avatar || profile.avatar_url || '',
        nickname: profile.nickname || '',
        campus: profile.campus || '',
        bio: profile.bio || ''
      }
    })
  },
  onInput(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
  },
  chooseAvatar() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath
        api.uploadFile({ url: '/files/upload', filePath, loading: true }).then((data) => {
          this.setData({ 'form.avatar': data.url })
        })
      }
    })
  },
  saveProfile() {
    api.put('/users/me', this.data.form, { loading: true }).then((user) => {
      saveAuth(getToken(), user)
      wx.showToast({ title: '资料已保存', icon: 'success' })
      wx.navigateBack()
    })
  }
})
