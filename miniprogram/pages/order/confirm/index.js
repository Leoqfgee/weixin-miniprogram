const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    productId: '',
    quantity: 1,
    product: null,
    meetLocation: '图书馆门口'
  },
  onLoad(options) {
    requireLogin()
    this.setData({
      productId: options.product_id || '',
      quantity: Number(options.quantity || 1)
    })
    this.loadProduct()
  },
  loadProduct() {
    if (!this.data.productId) return
    api.get(`/products/${this.data.productId}`, {}, { loading: true }).then((data) => {
      this.setData({ product: data })
    })
  },
  onLocationInput(event) {
    this.setData({ meetLocation: event.detail.value })
  },
  onCreateOrder() {
    const idempotencyKey = Date.now().toString(36) + Math.random().toString(36).slice(2)
    api.post('/orders', {
      product_id: this.data.productId,
      quantity: this.data.quantity,
      delivery_type: 'meetup',
      meet_location: this.data.meetLocation
    }, {
      loading: true,
      header: { 'X-Idempotency-Key': idempotencyKey }
    }).then((order) => {
      wx.redirectTo({ url: `/pages/order/detail/index?id=${order.id}` })
    })
  }
})
