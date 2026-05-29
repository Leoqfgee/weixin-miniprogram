const api = require('../../utils/request')
const { saveAuth } = require('../../utils/auth')

Page({
  data: {
    phone: '18800000002',
    password: 'buyer123456',
    selectedAccountIndex: 0,
    accounts: [
      { label: '买家', phone: '18800000002', password: 'buyer123456', mock_openid: 'mock_buyer_openid' },
      { label: '卖家', phone: '18800000001', password: 'seller123456', mock_openid: 'mock_seller_openid' },
      { label: '管理员', phone: '18800000000', password: 'admin123456', mock_openid: 'mock_admin_openid' }
    ]
  },
  onPhoneInput(event) {
    this.setData({ phone: event.detail.value })
  },
  onPasswordInput(event) {
    this.setData({ password: event.detail.value })
  },
  useAccount(event) {
    const item = this.data.accounts[event.currentTarget.dataset.index]
    this.setData({ phone: item.phone, password: item.password, selectedAccountIndex: event.currentTarget.dataset.index })
  },
  onWechatLogin() {
    const account = this.data.accounts[this.data.selectedAccountIndex]
    wx.login({
      success: (res) => {
        api.post('/auth/wechat-login', {
          code: res.code,
          mock_openid: account.mock_openid,
          nickname: account.label
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
    api.post('/auth/mock-login', {
      phone: this.data.phone,
      password: this.data.password
    }, { loading: true, loadingText: '登录中' }).then((data) => {
      saveAuth(data.token, data.user)
      wx.showToast({ title: '登录成功', icon: 'success' })
      wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) })
    })
  }
})
