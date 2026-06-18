const api = require('../../../utils/request')
const { getToken, getUser, clearAuth, hasRole, saveAuth } = require('../../../utils/auth')

Page({
  data: {
    user: null,
    isAdmin: false,
    avatarText: '?'
  },
  onShow() {
    const user = getUser()
    this.applyUser(user)
    if (!getToken()) return
    api.get('/users/me').then((freshUser) => {
      saveAuth(getToken(), freshUser)
      this.applyUser(freshUser)
    })
  },
  applyUser(user) {
    const nickname = user && user.profile ? user.profile.nickname || '我' : '?'
    this.setData({ user, isAdmin: hasRole('admin'), avatarText: nickname.slice(0, 1) })
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
  goAdminReports() {
    wx.navigateTo({ url: '/pages/admin/reports/index' })
  },
  goRefunds() {
    wx.navigateTo({ url: '/pages/refund/list/index?role=seller' })
  },
  goPublished() {
    wx.navigateTo({ url: '/pages/mine/published/index' })
  },
  goBought() {
    wx.navigateTo({ url: '/pages/order/bought/index' })
  },
  goSold() {
    wx.navigateTo({ url: '/pages/order/sold/index' })
  },
  goFavorites() {
    wx.navigateTo({ url: '/pages/favorite/index' })
  },
  goAddresses() {
    wx.navigateTo({ url: '/pages/address/index' })
  },
  goCustomerService() {
    wx.navigateTo({ url: '/pages/customer-service/index' })
  },
  goProfileEdit() {
    wx.navigateTo({ url: '/pages/profile/edit/index' })
  },
  goProfileHome() {
    const user = this.data.user
    if (!user) return
    wx.navigateTo({ url: `/pages/profile/home/index?id=${user.id}` })
  },
  logout() {
    clearAuth()
    this.setData({ user: null, isAdmin: false })
    wx.showToast({ title: '已退出', icon: 'success' })
  }
})
