const api = require('../../../utils/request')
const { getLoginType, getToken, getUser, requireLogin, saveAuth } = require('../../../utils/auth')

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
    },
    canUseWechatAvatar: false,
    avatarUploading: false,
    avatarUploadError: false
  },
  onLoad(options) {
    this.setData({ completeMode: options && options.mode === 'complete' })
  },
  onShow() {
    if (!requireLogin()) return
    const user = getUser()
    const profile = (user && user.profile) || {}
    const loginType = getLoginType()
    this.setData({
      canUseWechatAvatar: loginType === 'wechat',
      avatarUploading: false,
      avatarUploadError: false,
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
    const field = event.currentTarget.dataset.field
    let value = event.detail.value
    if (field === 'contact_phone') {
      value = String(value || '').replace(/\D/g, '').slice(0, 11)
    }
    this.setData({ [`form.${field}`]: value })
  },
  onChooseWechatAvatar(event) {
    if (!this.data.canUseWechatAvatar) {
      wx.showToast({ title: '当前账号不支持微信头像', icon: 'none' })
      return
    }
    const filePath = event.detail.avatarUrl
    if (!filePath) return
    this.setData({
      'form.avatar': filePath,
      'form.identity_type': 'wechat',
      avatarUploading: true,
      avatarUploadError: false
    })
    api.uploadImageBase64({ filePath, usage: 'avatar', loading: true }).then((data) => {
      this.setData({
        'form.avatar': withCacheBuster(data.url),
        'form.identity_type': 'wechat',
        avatarUploading: false,
        avatarUploadError: false
      })
    }).catch(() => {
      this.setData({ avatarUploading: false, avatarUploadError: true })
      wx.showToast({ title: '头像上传失败，请重试', icon: 'none' })
    })
  },
  openAvatarSheet() {
    wx.showActionSheet({
      itemList: ['从相册选择', '拍照'],
      success: (res) => {
        this.chooseAvatar(res.tapIndex === 1 ? 'camera' : 'album')
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
        this.setData({
          'form.avatar': filePath,
          'form.identity_type': 'custom',
          avatarUploading: true,
          avatarUploadError: false
        })
        api.uploadImageBase64({ filePath, usage: 'avatar', loading: true }).then((data) => {
          this.setData({
            'form.avatar': withCacheBuster(data.url),
            'form.identity_type': 'custom',
            avatarUploading: false,
            avatarUploadError: false
          })
        }).catch(() => {
          this.setData({ avatarUploading: false, avatarUploadError: true })
          wx.showToast({ title: '头像上传失败，请重试', icon: 'none' })
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
    if (this.data.avatarUploading) {
      wx.showToast({ title: '头像上传中，请稍后保存', icon: 'none' })
      return
    }
    if (this.data.avatarUploadError || isLocalTempFile(form.avatar)) {
      wx.showToast({ title: '头像上传失败，请重新选择', icon: 'none' })
      return
    }
    const contactPhone = String(form.contact_phone || '').trim()
    if (contactPhone && !/^1[3-9]\d{9}$/.test(contactPhone)) {
      wx.showToast({ title: '手机号格式不正确，请填写 11 位手机号', icon: 'none' })
      return
    }
    api.put('/users/me', {
      avatar_url: form.avatar,
      nickname: form.nickname,
      campus: form.campus,
      bio: form.bio,
      contact_phone: contactPhone,
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

function withCacheBuster(url) {
  const value = String(url || '').trim()
  if (!value) return ''
  return `${value}${value.indexOf('?') >= 0 ? '&' : '?'}v=${Date.now()}`
}

function isLocalTempFile(url) {
  const value = String(url || '')
  return value.indexOf('wxfile://') === 0 || value.indexOf('http://tmp/') === 0 || value.indexOf('file://') === 0
}
