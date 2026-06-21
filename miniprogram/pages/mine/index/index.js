const api = require('../../../utils/request')
const { getToken, getUser, clearAuth, hasRole, saveAuth } = require('../../../utils/auth')
const { normalizeCampusText } = require('../../../utils/format')

Page({
  data: {
    user: null,
    isAdmin: false,
    avatarText: '?',
    stats: { published: 0, bought: 0, sold: 0, favorites: 0 }
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
    const normalizedUser = user ? Object.assign({}, user, {
      profile: Object.assign({}, user.profile || {}, {
        campus: normalizeCampusText(user.profile && user.profile.campus, '')
      })
    }) : null
    const nickname = user && user.profile ? user.profile.nickname || '我' : '?'
    const stats = (user && user.stats) || {}
    this.setData({
      user: normalizedUser,
      isAdmin: hasRole('admin'),
      avatarText: nickname.slice(0, 1),
      stats: {
        published: Number(stats.published || 0),
        bought: Number(stats.bought || 0),
        sold: Number(stats.sold || 0),
        favorites: Number(stats.favorites || 0)
      }
    })
  },
  goLogin() {
    wx.navigateTo({ url: '/pages/login/index' })
  },
  goAdminProducts() {
    wx.navigateTo({ url: '/pages/admin/products/index' })
  },
  goAdminReportHandle() {
    wx.navigateTo({ url: '/pages/admin/report-handle/index' })
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
    wx.navigateTo({ url: '/pages/refund/list/index' })
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
  goSettings() {
    wx.navigateTo({ url: '/pages/settings/index' })
  },
  goProfileEdit() {
    wx.navigateTo({ url: '/pages/profile/edit/index' })
  },
  goProfileHome() {
    const user = this.data.user
    if (!user) return
    wx.navigateTo({ url: `/pages/profile/home/index?id=${user.id}` })
  },
  goCredit() {
    wx.navigateTo({ url: '/pages/mine/credit/index' })
  },
  logout() {
    clearAuth()
    this.setData({ user: null, isAdmin: false, stats: { published: 0, bought: 0, sold: 0, favorites: 0 } })
    wx.showToast({ title: '已退出', icon: 'success' })
  }
})
