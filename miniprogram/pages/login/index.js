const api = require('../../utils/request')
const { clearAuth, saveAuth } = require('../../utils/auth')
const { DEV_TEST_LOGIN_ENABLED } = require('../../utils/constants')

function validPhone(phone) {
  return /^1[3-9]\d{9}$/.test(String(phone || '').trim())
}

Page({
  data: {
    mode: 'login',
    phone: '',
    password: '',
    confirmPassword: '',
    nickname: '',
    showPhonePanel: false,
    devTestEnabled: DEV_TEST_LOGIN_ENABLED,
    testAccounts: [
      { key: 'buyer_a', label: '测试买家 A' },
      { key: 'buyer_b', label: '测试买家 B' },
      { key: 'admin', label: '测试管理员' }
    ]
  },

  afterLogin(data, title, loginType) {
    if (!data || !data.token || !data.user) {
      wx.showToast({ title: '登录结果异常，请重试', icon: 'none' })
      return
    }
    saveAuth(data.token, data.user, loginType)
    wx.showToast({ title: title || '登录成功', icon: 'success' })
    const user = data.user || {}
    const profile = user.profile || {}
    if (!user.profile_completed && !profile.profile_completed) {
      wx.redirectTo({ url: '/pages/profile/edit/index?mode=complete' })
      return
    }
    wx.switchTab({ url: '/pages/index/index' })
  },

  switchMode(event) {
    this.setData({ mode: event.currentTarget.dataset.mode, showPhonePanel: true })
  },

  openPhonePanel(event) {
    this.setData({ mode: event.currentTarget.dataset.mode || 'login', showPhonePanel: true })
  },

  closePhonePanel() {
    this.setData({ showPhonePanel: false })
  },

  setField(event) {
    this.setData({ [event.currentTarget.dataset.field]: event.detail.value })
  },

  validateForm() {
    const phone = this.data.phone.trim()
    const password = this.data.password
    if (!phone) return '手机号不能为空'
    if (!validPhone(phone)) return '手机号格式不正确'
    if (!password) return '密码不能为空'
    if (password.length < 6) return '密码至少 6 位'
    if (this.data.mode === 'register' && this.data.confirmPassword !== password) {
      return '两次输入的密码不一致'
    }
    return ''
  },

  submitPassword() {
    const error = this.validateForm()
    if (error) {
      wx.showToast({ title: error, icon: 'none' })
      return
    }
    clearAuth()
    const phone = this.data.phone.trim()
    const password = this.data.password
    if (this.data.mode === 'register') {
      api.post('/auth/register', {
        phone,
        password,
        nickname: this.data.nickname.trim()
      }, { loading: true, loadingText: '注册中' }).then((data) => {
        this.afterLogin(data, '注册成功', 'phone')
      })
      return
    }
    api.post('/auth/password-login', { phone, password }, { loading: true, loadingText: '登录中' }).then((data) => {
      this.afterLogin(data, '登录成功', 'phone')
    })
  },

  onWechatLogin() {
    wx.login({
      success: (res) => {
        if (!res.code) {
          wx.showToast({ title: '未获取到微信登录凭证', icon: 'none' })
          return
        }
        clearAuth()
        api.post('/auth/wechat-login', { code: res.code }, { loading: true, loadingText: '微信登录中' })
          .then((data) => this.afterLogin(data, '登录成功', 'wechat'))
      },
      fail: () => {
        wx.showToast({ title: '微信登录失败，请稍后重试', icon: 'none' })
      }
    })
  },

  onDevLogin(event) {
    clearAuth()
    this.setData({ phone: '', password: '', confirmPassword: '', mode: 'login' })
    api.post('/auth/dev-test-login', {
      account: event.currentTarget.dataset.account
    }, { loading: true, loadingText: '切换测试账号' }).then((data) => {
      this.afterLogin(data, '已切换账号', 'phone')
    })
  }
})
