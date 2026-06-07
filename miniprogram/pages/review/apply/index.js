const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: { orderId: '', rating: 5, content: '', anonymous: false },
  onLoad(options) {
    requireLogin()
    this.setData({ orderId: options.order_id || '' })
  },
  chooseRating(event) {
    this.setData({ rating: Number(event.currentTarget.dataset.value) })
  },
  onInput(event) {
    this.setData({ content: event.detail.value })
  },
  toggleAnonymous(event) {
    this.setData({ anonymous: event.detail.value })
  },
  submit() {
    api.post('/reviews', {
      order_id: this.data.orderId,
      rating: this.data.rating,
      content: this.data.content.trim(),
      anonymous: this.data.anonymous
    }, { loading: true }).then(() => {
      wx.showToast({ title: '评价已发布', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    })
  }
})
