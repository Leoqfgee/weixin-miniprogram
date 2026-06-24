const api = require('../../../utils/request')
const { getToken, getUser, clearAuth, hasRole, saveAuth } = require('../../../utils/auth')
const { normalizeCampusText } = require('../../../utils/format')

function normalizeScore(value) {
  if (value === 0 || value === '0') return 0
  if (value === undefined || value === null || value === '') return 100
  const score = Number(value)
  if (Number.isNaN(score)) return 100
  return Math.max(0, Math.min(100, score))
}

function mergeUserCredit(user, credit) {
  const base = Object.assign({}, user || {})
  const score = normalizeScore(credit && credit.credit_score !== undefined ? credit.credit_score : base.credit_score)
  const level = (credit && credit.credit_level) || base.credit_level || (score === 100 ? '信用优秀' : score >= 90 ? '信用良好' : score >= 70 ? '信用一般' : score >= 60 ? '信用偏低' : '限制发布')
  base.credit_score = score
  base.credit_level = level
  base.credit = Object.assign({}, base.credit || {}, credit || {}, {
    credit_score: score,
    credit_level: level
  })
  base.profile = Object.assign({}, base.profile || {}, {
    credit_score: score,
    credit_level: level
  })
  return base
}

Page({
  data: {
    user: null,
    isAdmin: false,
    avatarText: '?',
    creditScore: 100,
    creditLevel: '信用优秀',
    stats: { published: 0, bought: 0, sold: 0, favorites: 0 }
  },
  onShow() {
    const cachedUser = getUser()
    this.applyUser(cachedUser)
    const token = getToken()
    if (!token) return

    Promise.all([
      api.get('/users/me', {}, { silentError: true }),
      api.get('/users/me/credit', {}, { silentError: true })
    ]).then(([freshUser, credit]) => {
      const mergedUser = mergeUserCredit(freshUser, credit)
      saveAuth(token, mergedUser)
      this.applyUser(mergedUser)
    }).catch(() => {
      api.get('/users/me/credit', {}, { silentError: true }).then((credit) => {
        const mergedUser = mergeUserCredit(this.data.user || getUser() || {}, credit)
        saveAuth(token, mergedUser)
        this.applyUser(mergedUser)
      })
    })
  },
  applyUser(user) {
    const score = normalizeScore(user && (user.credit_score !== undefined ? user.credit_score : user.profile && user.profile.credit_score))
    const level = (user && (user.credit_level || (user.profile && user.profile.credit_level))) || (score === 100 ? '信用优秀' : score >= 90 ? '信用良好' : score >= 70 ? '信用一般' : score >= 60 ? '信用偏低' : '限制发布')
    const normalizedUser = user ? Object.assign({}, user, {
      credit_score: score,
      credit_level: level,
      profile: Object.assign({}, user.profile || {}, {
        campus: normalizeCampusText(user.profile && user.profile.campus, ''),
        credit_score: score,
        credit_level: level
      })
    }) : null
    const nickname = user && user.profile ? user.profile.nickname || '我' : '?'
    const stats = (user && user.stats) || {}
    this.setData({
      user: normalizedUser,
      isAdmin: hasRole('admin'),
      avatarText: nickname.slice(0, 1),
      creditScore: score,
      creditLevel: level,
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
  goAdminStudentVerification() {
    wx.navigateTo({ url: '/pages/admin/student-verification/index' })
  },
  goAdminContentModeration() {
    wx.navigateTo({ url: '/pages/admin/content-moderation/index' })
  },
  goAdminCreditAdjust() {
    wx.navigateTo({ url: '/pages/admin/credit-adjust/index' })
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
  goStudentVerification() {
    wx.navigateTo({ url: '/pages/student-verification/apply/index' })
  },
  logout() {
    clearAuth()
    this.setData({ user: null, isAdmin: false, creditScore: 100, creditLevel: '信用优秀', stats: { published: 0, bought: 0, sold: 0, favorites: 0 } })
    wx.showToast({ title: '已退出', icon: 'success' })
  }
})
