const { DEFAULT_PRODUCT_IMAGE, normalizeImageMeta } = require('../../utils/image')
const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')
const { safeText, formatMoney, normalizeCampusText, productStatusText, conditionText } = require('../../utils/format')

const IMAGE_GUARD_VERSION = '20260620-ui-card-safe'

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
    conditionText: '',
    campusText: '\u6821\u5185',
    categoryText: '\u5176\u4ed6',
    statusText: '\u5728\u552e',
    displayTitle: '\u672a\u547d\u540d\u5546\u54c1',
    displayPrice: '\uffe50',
    sellerText: '\u6821\u56ed\u540c\u5b66',
    stockText: '0',
    viewText: '0',
    coverImage: '',
    coverText: '\u5546\u54c1',
    coverFailed: false,
    savingFavorite: false
  },
  lifetimes: { attached() { this.prepareProduct(this.data.product || {}) } },
  methods: {
    prepareProduct(product) {
      const images = Array.isArray(product.images) ? product.images : []
      const title = safeText(product.title, '\u672a\u547d\u540d\u5546\u54c1')
      const rawImage = product.cover_image || images[0] || ''
      const imageMeta = isLegacyUploadUrl(rawImage) ? { url: DEFAULT_PRODUCT_IMAGE, legacy: true } : normalizeImageMeta(rawImage, 'product')
      if (imageMeta.url === DEFAULT_PRODUCT_IMAGE && rawImage) console.warn('[product-card fallback]', IMAGE_GUARD_VERSION, product.id || '', title, rawImage)
      this.setData({
        conditionText: conditionText(product.condition),
        campusText: normalizeCampusText(product.campus || (product.seller && product.seller.campus), '\u6821\u5185'),
        categoryText: safeText(product.category_name, '\u5176\u4ed6'),
        statusText: productStatusText(product.status || 'on_sale'),
        displayTitle: title,
        displayPrice: formatMoney(product.price),
        sellerText: safeText(product.seller && product.seller.nickname, '\u6821\u56ed\u540c\u5b66'),
        stockText: String(Number(product.stock || product.inventory || product.quantity || product.count || product.available_stock || 1)),
        viewText: String(Number(product.view_count || 0)),
        coverImage: imageMeta.url,
        coverText: title.slice(0, 2),
        coverFailed: false
      })
    },
    onCoverError() {
      const product = this.data.product || {}
      const images = Array.isArray(product.images) ? product.images : []
      console.warn('[product-card fallback]', IMAGE_GUARD_VERSION, product.id || '', product.title || '', product.cover_image || images[0] || 'binderror')
      this.setData({ coverImage: DEFAULT_PRODUCT_IMAGE, coverFailed: false })
    },
    onTap() {
      const id = this.data.product && this.data.product.id
      if (id) wx.navigateTo({ url: `/pages/product/detail/index?id=${id}` })
    },
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
