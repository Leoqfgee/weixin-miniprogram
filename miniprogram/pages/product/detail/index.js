const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { DEFAULT_AVATAR_IMAGE, DEFAULT_PRODUCT_IMAGE, normalizeImageList, normalizeImageUrl } = require('../../../utils/image')
const { safeText, formatMoney, normalizeCampusText, productStatusText, conditionText } = require('../../../utils/format')

Page({
  data: {
    id: '',
    product: null,
    gallery: [],
    recommendations: [],
    currentImage: 0,
    conditionText: '',
    coverText: '闲置',
    quantity: 1,
    descExpanded: false
  },
  onLoad(options) {
    this.setData({ id: options.id || '' })
    this.loadProduct()
  },
  onShow() {
    if (this.data.id && this.data.product) this.loadProduct()
  },
  loadProduct() {
    api.get(`/products/${this.data.id}`, {}, { loading: true }).then((product) => {
      const seller = product.seller || {}
      const sellerAvatar = normalizeImageUrl(seller.avatar || seller.avatar_url, 'avatar')
      this.setData({
        product: Object.assign({}, product, {
          display_title: safeText(product.title, '\u672a\u547d\u540d\u5546\u54c1'),
          display_price: formatMoney(product.price),
          display_status: productStatusText(product.status || 'on_sale'),
          display_campus: normalizeCampusText(product.campus || seller.campus, '\u6821\u5185'),
          display_category: safeText(product.category_name, '\u5176\u4ed6'),
          display_stock: Number(product.stock || 0),
          display_views: Number(product.view_count || 0),
          display_favorites: Number(product.favorite_count || 0),
          display_description: safeText(product.description, '\u5356\u5bb6\u6682\u672a\u586b\u5199\u63cf\u8ff0'),
          seller: Object.assign({}, seller, {
            avatar: sellerAvatar,
            avatar_url: sellerAvatar,
            display_name: safeText(seller.nickname, '\u6821\u56ed\u540c\u5b66'),
            display_campus: normalizeCampusText(seller.campus || product.campus, '\u6821\u5185\u4ea4\u6613'),
            display_credit: Number(seller.credit_score || 100)
          })
        }),
        gallery: normalizeImageList(product.images && product.images.length ? product.images : [product.cover_image], 'product'),
        conditionText: conditionText(product.condition),
        coverText: safeText(product.title, '\u95f2\u7f6e\u597d\u7269').slice(0, 4)
      })
      this.loadRecommendations()
    })
  },
  loadRecommendations() {
    if (!this.data.id) return
    api.get(`/products/${this.data.id}/recommendations`, { limit: 6 }, { silentError: true }).then((data) => {
      this.setData({ recommendations: data.items || [] })
    }).catch(() => {
      this.setData({ recommendations: [] })
    })
  },
  onImageChange(event) {
    this.setData({ currentImage: event.detail.current || 0 })
  },
  onGalleryImageError(event) {
    const index = Number(event.currentTarget.dataset.index || 0)
    const gallery = this.data.gallery.slice()
    gallery[index] = DEFAULT_PRODUCT_IMAGE
    this.setData({ gallery })
  },
  previewGallery(event) {
    const gallery = (this.data.gallery || []).filter(Boolean)
    if (!gallery.length) return
    const index = Number(event.currentTarget.dataset.index || this.data.currentImage || 0)
    wx.previewImage({
      current: gallery[index] || gallery[0],
      urls: gallery
    })
  },
  onSellerAvatarError() {
    this.setData({
      'product.seller.avatar': DEFAULT_AVATAR_IMAGE,
      'product.seller.avatar_url': DEFAULT_AVATAR_IMAGE
    })
  },
  toggleDescription() {
    this.setData({ descExpanded: !this.data.descExpanded })
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
    wx.navigateTo({ url: `/pages/message/chat/index?receiver_id=${product.seller.id}&product_id=${product.id}&product_title=${encodeURIComponent(product.title || '')}&product_price=${product.price || ''}&product_cover=${encodeURIComponent(normalizeImageUrl(product.cover_image, 'product'))}` })
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
  },
  onShareAppMessage() {
    const product = this.data.product || {}
    return {
      title: product.title ? `校园二手：${product.title}` : '校园二手好物',
      path: `/pages/product/detail/index?id=${product.id || this.data.id}`,
      imageUrl: (this.data.gallery && this.data.gallery[0]) || product.cover_image || ''
    }
  }
})
