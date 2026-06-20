const api = require('../../../utils/request')
const { safeText } = require('../../../utils/format')

Page({
  data: { id: '', profile: null, avatarText: '', products: [], reviews: [] },
  onLoad(options) { this.setData({ id: options.id || '' }); this.loadProfile() },
  loadProfile() {
    if (!this.data.id) return
    api.get(`/users/${this.data.id}/profile`, {}, { loading: true }).then((data) => {
      const profile = data.user || {}
      this.setData({ profile: Object.assign({}, profile, { nickname: safeText(profile.nickname, '校内同学'), campus: safeText(profile.campus, '未填写校区'), publish_count: Number(profile.publish_count || 0), deal_count: Number(profile.deal_count || 0), good_rate: Number(profile.good_rate || 0), credit_score: Number(profile.credit_score || 100), review_count: Number(profile.review_count || 0), bio: safeText(profile.bio, '暂无简介') }), avatarText: safeText(profile.nickname, '校').slice(0, 1), products: data.on_sale_products || [], reviews: data.reviews || [] })
    })
  },
  viewReview(event) { wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` }) }
})
