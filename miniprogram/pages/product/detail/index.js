const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    id: '',
    product: null,
    conditionText: '',
    coverText: '闲置',
    quantity: 1
  },
  onLoad(options) {
    this.setData({ id: options.id || '' })
    this.loadProduct()
  },
  loadProduct() {
    if (!this.data.id) return
    api.get(`/products/${this.data.id}`, {}, { loading: true }).then((data) => {
      const conditionMap = {
        new: '全新',
        like_new: '几乎全新',
        good: '成色良好',
        fair: '有使用痕迹'
      }
      this.setData({
        product: data,
        conditionText: conditionMap[data.condition] || '校内闲置',
        coverText: (data.title || '闲置好物').slice(0, 4)
      })
    })
  },
  addCart() {
    if (!requireLogin()) return
    api.post('/cart/items', {
      product_id: this.data.id,
      quantity: this.data.quantity
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已加入购物车', icon: 'success' })
    })
  },
  buyNow() {
    if (!requireLogin()) return
    wx.navigateTo({ url: `/pages/order/confirm/index?product_id=${this.data.id}&quantity=${this.data.quantity}` })
  },
  contactSeller() {
    if (!requireLogin()) return
    const product = this.data.product
    api.post('/messages', {
      receiver_id: product.seller.id,
      product_id: product.id,
      content: `我想咨询「${product.title}」`
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已发送消息', icon: 'success' })
    })
  },
  offShelf() {
    wx.showModal({
      title: '确认下架',
      content: '下架后买家将不能继续购买该商品。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${this.data.id}/off-shelf`, { reason: '小程序端下架' }, { loading: true })
          .then(() => {
            wx.showToast({ title: '已下架', icon: 'success' })
            this.loadProduct()
          })
      }
    })
  }
})
