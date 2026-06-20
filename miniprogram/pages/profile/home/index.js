const api = require('../../../utils/request')
const { safeText, normalizeCampusText } = require('../../../utils/format')

Page({
  data: {
    id: '',
    profile: null,
    avatarText: '',
    products: [],
    reviews: []
  },
  onLoad(options) {
    this.setData({ id: options.id || '' })
    this.loadProfile()
  },
  loadProfile() {
    if (!this.data.id) return
    api.get(`/users/${this.data.id}/profile`, {}, { loading: true }).then((data) => {
      const profile = Object.assign({}, data.user || {})
      profile.nickname = safeText(profile.nickname, '\u6821\u56ed\u540c\u5b66')
      profile.campus = normalizeCampusText(profile.campus, '\u672a\u586b\u5199\u6821\u533a')
      profile.bio = safeText(profile.bio, '\u6682\u65e0\u7b80\u4ecb')
      profile.publish_count = Number(profile.publish_count || 0)
      profile.deal_count = Number(profile.deal_count || 0)
      profile.good_rate = Number(profile.good_rate || 0)
      profile.credit_score = Number(profile.credit_score || 100)
      this.setData({
        profile,
        avatarText: (profile.nickname || '校').slice(0, 1),
        products: (data.on_sale_products || []).map((item) => Object.assign({}, item, { stock: item.stock || item.inventory || item.quantity || item.count || item.available_stock || 1 })),
        reviews: data.reviews || []
      })
    })
  },
  viewReview(event) {
    wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` })
  }
})
