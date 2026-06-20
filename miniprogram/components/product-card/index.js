const { DEFAULT_PRODUCT_IMAGE, normalizeImageMeta } = require('../../utils/image')
const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')
const { safeText, money, productStatus, condition } = require('../../utils/format')
const IMAGE_GUARD_VERSION = '20260620-ui-reference-card'
function isLegacyUploadUrl(url) {
  const value = String(url || '')
  return value.indexOf('/uploads/') >= 0 || value.indexOf('/uploads/demo/') >= 0 || value.indexOf('124.223.146.85') >= 0 || value.indexOf('flask-fnnj') >= 0 || value.indexOf('tcloudbase.com/uploads/') >= 0
}
Component({
  properties: {
    product: { type: Object, value: {}, observer(value) { this.prepareProduct(value || {}) } },
    layout: { type: String, value: 'list' }
  },
  data: {
    conditionText: '', campusText: '', categoryText: '其他', statusText: '在售', displayTitle: '未命名商品', displayPrice: '￥0', sellerText: '校内同学', stockText: '0', viewText: '0', coverImage: '', coverText: '闲置', coverFailed: false, savingFavorite: false
  },
  lifetimes: { attached() { this.prepareProduct(this.data.product || {}) } },
  methods: {
    prepareProduct(product) {
      const images = Array.isArray(product.images) ? product.images : []
      const title = safeText(product.title, '未命名商品')
      const rawImage = product.cover_image || images[0] || ''
      const imageMeta = isLegacyUploadUrl(rawImage) ? { url: DEFAULT_PRODUCT_IMAGE, legacy: true } : normalizeImageMeta(rawImage, 'product')
      if (imageMeta.url === DEFAULT_PRODUCT_IMAGE && rawImage) console.warn('[product-card fallback]', IMAGE_GUARD_VERSION, product.id || '', title, rawImage)
      this.setData({ conditionText: condition(product.condition), campusText: safeText(product.campus || (product.seller && product.seller.campus), '校内'), categoryText: safeText(product.category_name, '其他'), statusText: productStatus(product.status || 'on_sale'), displayTitle: title, displayPrice: money(product.price), sellerText: safeText(product.seller && product.seller.nickname, '校内同学'), stockText: String(Number(product.stock || 0)), viewText: String(Number(product.view_count || 0)), coverImage: imageMeta.url, coverText: title.slice(0, 2), coverFailed: false })
    },
    onCoverError() {
      const product = this.data.product || {}
      const images = Array.isArray(product.images) ? product.images : []
      console.warn('[product-card fallback]', IMAGE_GUARD_VERSION, product.id || '', product.title || '', product.cover_image || images[0] || 'binderror')
      this.setData({ coverImage: DEFAULT_PRODUCT_IMAGE, coverFailed: false })
    },
    onTap() { const id = this.data.product && this.data.product.id; if (id) wx.navigateTo({ url: `/pages/product/detail/index?id=${id}` }) },
    toggleFavorite() {
      const product = this.data.product || {}
      if (!product.id || this.data.savingFavorite) return
      if (!requireLogin()) return
      this.setData({ savingFavorite: true })
      const nextFavorited = !product.is_favorited
      const request = product.is_favorited ? api.del(`/favorites/${product.id}`) : api.post('/favorites', { product_id: product.id })
      request.then(() => {
        const favoriteCount = Math.max(0, Number(product.favorite_count || 0) + (nextFavorited ? 1 : -1))
        this.setData({ product: Object.assign({}, product, { is_favorited: nextFavorited, favorite_count: favoriteCount }) })
        this.triggerEvent('favoritechange', { id: product.id, is_favorited: nextFavorited, favorite_count: favoriteCount })
      }).finally(() => this.setData({ savingFavorite: false }))
    }
  }
})
