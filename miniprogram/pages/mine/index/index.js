const api = require('../../../utils/request')
const { getToken, getUser, clearAuth, hasRole, saveAuth } = require('../../../utils/auth')
const { safeText } = require('../../../utils/format')

Page({
  data: { user: null, isAdmin: false, avatarText: '?', stats: { published: 0, bought: 0, sold: 0, favorites: 0 }, profileRate: '0%', tradeItems: [], serviceItems: [] },
  onShow() { const user = getUser(); this.applyUser(user); if (!getToken()) return; api.get('/users/me').then((freshUser) => { saveAuth(getToken(), freshUser); this.applyUser(freshUser) }) },
  applyUser(user) {
    const profile = (user && user.profile) || {}
    const nickname = safeText(profile.nickname, '我')
    const stats = (user && user.stats) || {}
    this.setData({
      user, isAdmin: hasRole('admin'), avatarText: nickname.slice(0, 1), profileRate: profile.profile_completed ? '100%' : '60%',
      stats: { published: Number(stats.published || 0), bought: Number(stats.bought || 0), sold: Number(stats.sold || 0), favorites: Number(stats.favorites || 0) },
      tradeItems: [
        { text: '发布的', icon: '/assets/tabbar/publish-active.png', action: 'goPublished' },
        { text: '我买到的', icon: '/assets/tabbar/home-active.png', action: 'goBought' },
        { text: '我卖出的', icon: '/assets/tabbar/message-active.png', action: 'goSold' }
      ],
      serviceItems: [
        { text: '我的收藏', icon: '/assets/tabbar/home.png', action: 'goFavorites' },
        { text: '收货地址', icon: '/assets/tabbar/mine-active.png', action: 'goAddresses' },
        { text: '售后', icon: '/assets/tabbar/message.png', action: 'goRefunds' },
        { text: '联系客服', icon: '/assets/tabbar/message-active.png', action: 'goCustomerService' },
        { text: '我的主页', icon: '/assets/tabbar/mine.png', action: 'goProfileHome' },
        { text: '设置', icon: '/assets/tabbar/publish.png', action: 'goSettings' }
      ]
    })
  },
  handleGridTap(event) { const action = event.currentTarget.dataset.action; if (action && this[action]) this[action]() },
  goLogin() { wx.navigateTo({ url: '/pages/login/index' }) },
  goAdminProducts() { wx.navigateTo({ url: '/pages/admin/products/index' }) },
  goAdminLogs() { wx.navigateTo({ url: '/pages/admin/logs/index' }) },
  goAdminAppeals() { wx.navigateTo({ url: '/pages/admin/appeals/index' }) },
  goAdminReports() { wx.navigateTo({ url: '/pages/admin/reports/index' }) },
  goRefunds() { wx.navigateTo({ url: '/pages/refund/list/index' }) },
  goPublished() { wx.navigateTo({ url: '/pages/mine/published/index' }) },
  goBought() { wx.navigateTo({ url: '/pages/order/bought/index' }) },
  goSold() { wx.navigateTo({ url: '/pages/order/sold/index' }) },
  goFavorites() { wx.navigateTo({ url: '/pages/favorite/index' }) },
  goAddresses() { wx.navigateTo({ url: '/pages/address/index' }) },
  goCustomerService() { wx.navigateTo({ url: '/pages/customer-service/index' }) },
  goSettings() { wx.navigateTo({ url: '/pages/settings/index' }) },
  goProfileEdit() { wx.navigateTo({ url: '/pages/profile/edit/index' }) },
  goProfileHome() { const user = this.data.user; if (user) wx.navigateTo({ url: `/pages/profile/home/index?id=${user.id}` }) },
  logout() { clearAuth(); this.setData({ user: null, isAdmin: false, stats: { published: 0, bought: 0, sold: 0, favorites: 0 } }); wx.showToast({ title: '已退出', icon: 'success' }) }
})
