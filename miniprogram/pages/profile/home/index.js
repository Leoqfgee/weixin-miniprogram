const api = require('../../../utils/request')

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
      const profile = data.user || {}
      this.setData({
        profile,
        avatarText: (profile.nickname || '校').slice(0, 1),
        products: data.on_sale_products || [],
        reviews: data.reviews || []
      })
    })
  },
  viewReview(event) {
    wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` })
  }
})
