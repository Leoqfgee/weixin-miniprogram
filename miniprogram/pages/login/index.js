const api = require('../../utils/request')
const { saveAuth } = require('../../utils/auth')

Page({
  data: {
    phone: '18800000002',
    password: 'buyer123456',
    accounts: [
      { label: '买家', phone: '18800000002', password: 'buyer123456' },
      { label: '卖家', phone: '18800000001', password: 'seller123456' },
      { label: '管理员', phone: '18800000000', password: 'admin123456' }
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
    this.setData({ phone: item.phone, password: item.password })
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
