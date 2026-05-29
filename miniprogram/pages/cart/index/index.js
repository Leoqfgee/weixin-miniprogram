const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    items: []
  },
  onLoad() {
    requireLogin()
    this.loadCart()
  },
  onShow() {
    if (requireLogin()) {
      this.loadCart()
    }
  },
  loadCart() {
    api.get('/cart', {}, { loading: true }).then((data) => {
      this.setData({ items: data.items || [] })
    })
  },
  changeQuantity(event) {
    const productId = event.currentTarget.dataset.id
    const quantity = Number(event.detail.value)
    if (!quantity || quantity <= 0) return
    api.put(`/cart/items/${productId}`, { quantity }).then(() => this.loadCart())
  },
  deleteItem(event) {
    const productId = event.currentTarget.dataset.id
    api.del(`/cart/items/${productId}`).then(() => this.loadCart())
  },
  onCheckout(event) {
    const productId = event.currentTarget.dataset.id
    const quantity = event.currentTarget.dataset.quantity
    wx.navigateTo({ url: `/pages/order/confirm/index?product_id=${productId}&quantity=${quantity}` })
  }
})
