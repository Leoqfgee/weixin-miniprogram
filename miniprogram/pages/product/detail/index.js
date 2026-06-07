const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: { id: '', product: null, conditionText: '', coverText: '闲置', quantity: 1 },
  onLoad(options) {
    this.setData({ id: options.id || '' })
    this.loadProduct()
  },
  onShow() {
    if (this.data.id && this.data.product) this.loadProduct()
  },
  loadProduct() {
    api.get(`/products/${this.data.id}`, {}, { loading: true }).then((product) => {
      const conditionMap = { new: '全新', like_new: '几乎全新', good: '成色良好', fair: '有使用痕迹' }
      this.setData({
        product,
        conditionText: conditionMap[product.condition] || '成色未填写',
        coverText: (product.title || '闲置好物').slice(0, 4)
      })
    })
  },
  buyNow() {
    if (requireLogin()) wx.navigateTo({ url: `/pages/order/confirm/index?product_id=${this.data.id}&quantity=${this.data.quantity}` })
  },
  editProduct() {
    wx.navigateTo({ url: `/pages/publish/product-edit/index?id=${this.data.id}` })
  },
  contactSeller() {
    if (!requireLogin()) return
    const product = this.data.product
    wx.navigateTo({ url: `/pages/message/chat/index?receiver_id=${product.seller.id}&product_id=${product.id}&product_title=${encodeURIComponent(product.title || '')}&product_price=${product.price || ''}&product_cover=${encodeURIComponent(product.cover_image || '')}` })
  },
  toggleFavorite() {
    if (!requireLogin()) return
    const product = this.data.product
    const request = product.is_favorited ? api.del(`/favorites/${product.id}`) : api.post('/favorites', { product_id: product.id })
    request.then(() => this.loadProduct())
  },
  goSellerProfile() {
    const seller = this.data.product && this.data.product.seller
    if (seller && seller.id) wx.navigateTo({ url: `/pages/profile/home/index?id=${seller.id}` })
  },
  offShelf() {
    wx.showModal({
      title: '确认下架',
      content: '下架后买家将不能继续购买该商品。',
      success: (res) => {
        if (res.confirm) api.post(`/products/${this.data.id}/off-shelf`, { reason: '小程序端下架' }, { loading: true }).then(() => this.loadProduct())
      }
    })
  },
  republish() {
    wx.showModal({
      title: '重新发布商品',
      content: '商品将重新提交管理员审核，审核通过后恢复在售。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${this.data.id}/republish`, {}, { loading: true }).then(() => this.loadProduct())
      }
    })
  },
  deleteProduct() {
    wx.showModal({
      title: '删除商品',
      content: '删除后不会影响历史订单，但无法再从商品管理中查看。',
      confirmColor: '#C84A3A',
      success: (res) => {
        if (!res.confirm) return
        api.del(`/products/${this.data.id}`, {}, { loading: true }).then(() => {
          wx.showToast({ title: '已删除', icon: 'success' })
          setTimeout(() => wx.navigateBack(), 400)
        })
      }
    })
  }
})
