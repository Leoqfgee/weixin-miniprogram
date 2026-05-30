const { getUser, clearAuth, hasRole } = require('../../../utils/auth')

Page({
  data: {
    user: null,
    isAdmin: false
  },
  onShow() {
    const user = getUser()
    this.setData({ user, isAdmin: hasRole('admin') })
  },
  goLogin() {
    wx.navigateTo({ url: '/pages/login/index' })
  },
  goAdminProducts() {
    wx.navigateTo({ url: '/pages/admin/products/index' })
  },
  goAdminLogs() {
    wx.navigateTo({ url: '/pages/admin/logs/index' })
  },
  goAdminAppeals() {
    wx.navigateTo({ url: '/pages/admin/appeals/index' })
  },
  goCart() {
    wx.navigateTo({ url: '/pages/cart/index/index' })
  },
  goRefunds() {
    wx.navigateTo({ url: '/pages/refund/list/index' })
  },
  logout() {
    clearAuth()
    this.setData({ user: null, isAdmin: false })
    wx.showToast({ title: '已退出', icon: 'success' })
  }
})
