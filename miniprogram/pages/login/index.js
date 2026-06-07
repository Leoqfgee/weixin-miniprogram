const api = require('../../utils/request')
const { clearAuth, saveAuth } = require('../../utils/auth')
const { DEV_TEST_LOGIN_ENABLED } = require('../../utils/constants')

Page({
  data: {
    phone: '',
    password: '',
    showPasswordLogin: false,
    devTestEnabled: DEV_TEST_LOGIN_ENABLED,
    testAccounts: [
      { key: 'buyer_a', label: '测试买家 A' },
      { key: 'buyer_b', label: '测试买家 B' },
      { key: 'admin', label: '测试管理员' }
    ]
  },
  afterLogin(data) {
    saveAuth(data.token, data.user)
    wx.showToast({ title: '登录成功', icon: 'success' })
    const user = data.user || {}
    const profile = user.profile || {}
    if (!user.profile_completed && !profile.profile_completed) {
      wx.redirectTo({ url: '/pages/profile/edit/index?mode=complete' })
      return
    }
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) })
  },
  onPhoneInput(event) {
    this.setData({ phone: event.detail.value })
  },
  onPasswordInput(event) {
    this.setData({ password: event.detail.value })
  },
  togglePasswordLogin() {
    this.setData({ showPasswordLogin: !this.data.showPasswordLogin })
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
          this.afterLogin(data)
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
      this.afterLogin(data)
    })
  },
  onDevLogin(event) {
    clearAuth()
    this.setData({ phone: '', password: '', showPasswordLogin: false })
    api.post('/auth/dev-test-login', {
      account: event.currentTarget.dataset.account
    }, { loading: true, loadingText: '切换测试账号' }).then((data) => {
      this.afterLogin(data)
    })
  }
}
)
