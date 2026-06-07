const api = require('../../../utils/request')
const { getToken, getUser, requireLogin, saveAuth } = require('../../../utils/auth')

Page({
  data: {
    completeMode: false,
    form: {
      avatar: '',
      nickname: '',
      campus: '',
      bio: '',
      contact_phone: '',
      contact_wechat: '',
      identity_type: 'custom'
    }
  },
  onLoad(options) {
    this.setData({ completeMode: options && options.mode === 'complete' })
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
        bio: profile.bio || '',
        contact_phone: profile.contact_phone || '',
        contact_wechat: profile.contact_wechat || '',
        identity_type: profile.identity_type || user.identity_type || 'custom'
      }
    })
  },
  onInput(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
  },
  onChooseWechatAvatar(event) {
    const filePath = event.detail.avatarUrl
    if (!filePath) return
    api.uploadFile({ url: '/files/upload', filePath, loading: true }).then((data) => {
      this.setData({
        'form.avatar': data.url,
        'form.identity_type': 'wechat'
      })
    })
  },
  openAvatarSheet() {
    wx.showActionSheet({
      itemList: ['使用微信头像', '从相册选择', '拍照'],
      success: (res) => {
        if (res.tapIndex === 0) {
          wx.showToast({ title: '请点击下方微信头像按钮', icon: 'none' })
          return
        }
        this.chooseAvatar(res.tapIndex === 2 ? 'camera' : 'album')
      }
    })
  },
  chooseAvatar(sourceType) {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: [sourceType || 'album'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath
        api.uploadFile({ url: '/files/upload', filePath, loading: true }).then((data) => {
          this.setData({
            'form.avatar': data.url,
            'form.identity_type': 'custom'
          })
        })
      }
    })
  },
  saveProfile() {
    const form = this.data.form
    if (!form.nickname || !form.nickname.trim()) {
      wx.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }
    if (!form.avatar) {
      wx.showToast({ title: '请选择头像', icon: 'none' })
      return
    }
    api.put('/users/me', {
      avatar_url: form.avatar,
      nickname: form.nickname,
      campus: form.campus,
      bio: form.bio,
      contact_phone: form.contact_phone,
      contact_wechat: form.contact_wechat,
      identity_type: form.identity_type || 'custom'
    }, { loading: true }).then((user) => {
      saveAuth(getToken(), user)
      wx.showToast({ title: '资料已保存', icon: 'success' })
      if (this.data.completeMode) {
        wx.switchTab({ url: '/pages/mine/index/index' })
        return
      }
      wx.navigateBack()
    })
  }
})
