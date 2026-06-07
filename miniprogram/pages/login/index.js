const api = require('../../utils/request')
const { saveAuth } = require('../../utils/auth')

Page({
  data: {
    phone: '',
    password: ''
  },
  onPhoneInput(event) {
    this.setData({ phone: event.detail.value })
  },
  onPasswordInput(event) {
    this.setData({ password: event.detail.value })
  },
  onWechatLogin() {
    wx.login({
      success: (res) => {
        if (!res.code) {
          wx.showToast({ title: '未获取到微信登录凭证', icon: 'none' })
          return
        }
        api.post('/auth/wechat-login', {
          code: res.code
        }, { loading: true, loadingText: '微信登录中' }).then((data) => {
          saveAuth(data.token, data.user)
          wx.showToast({ title: '登录成功', icon: 'success' })
          wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) })
        })
      },
      fail: () => {
        wx.showToast({ title: '微信登录失败', icon: 'none' })
      }
    })
  },
  onLogin() {
    api.post('/auth/password-login', {
      phone: this.data.phone,
      password: this.data.password
    }, { loading: true, loadingText: '登录中' }).then((data) => {
      saveAuth(data.token, data.user)
      wx.showToast({ title: '登录成功', icon: 'success' })
      wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) })
    })
  }
}
)
