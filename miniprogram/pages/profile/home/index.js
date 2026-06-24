const api = require('../../../utils/request')
const { getUser } = require('../../../utils/auth')
const { safeText, normalizeCampusText } = require('../../../utils/format')

function normalizeScore(value) {
  if (value === 0 || value === '0') return 0
  if (value === undefined || value === null || value === '') return 100
  const score = Number(value)
  if (Number.isNaN(score)) return 100
  return Math.max(0, Math.min(100, score))
}

Page({
  data: {
    id: '',
    profile: null,
    avatarText: '',
    canReport: false,
    products: [],
    reviews: []
  },
  onLoad(options) {
    this.setData({ id: options.id || '' })
    this.loadProfile()
  },
  onShow() {
    if (this.data.id) this.loadProfile()
  },
  loadProfile() {
    if (!this.data.id) return
    api.get(`/users/${this.data.id}/profile`, {}, { loading: true }).then((data) => {
      const profile = Object.assign({}, data.user || {})
      profile.nickname = safeText(profile.nickname, '校园同学')
      profile.campus = normalizeCampusText(profile.campus, '未填写校区')
      profile.bio = safeText(profile.bio, '暂无简介')
      profile.publish_count = Number(profile.publish_count || 0)
      profile.deal_count = Number(profile.deal_count || 0)
      profile.good_rate = Number(profile.good_rate || 0)
      profile.credit_score = normalizeScore(profile.credit_score)
      profile.student_verify_status_text = profile.student_verify_status_text || (profile.student_verified ? '已认证' : '未认证')
      const currentUser = getUser() || {}
      this.setData({
        profile,
        avatarText: (profile.nickname || '校').slice(0, 1),
        canReport: !!currentUser.id && currentUser.id !== profile.id,
        products: (data.on_sale_products || []).map((item) => Object.assign({}, item, { stock: item.stock || item.inventory || item.quantity || item.count || item.available_stock || 1 })),
        reviews: data.reviews || []
      })
    })
  },
  reportUser() {
    if (!this.data.canReport || !this.data.profile) return
    wx.navigateTo({ url: `/pages/report/user-report/index?user_id=${this.data.profile.id}` })
  },
  viewReview(event) {
    wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` })
  }
})
