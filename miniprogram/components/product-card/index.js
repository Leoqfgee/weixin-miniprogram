const { DEFAULT_PRODUCT_IMAGE, normalizeImageMeta } = require('../../utils/image')
const IMAGE_GUARD_VERSION = '20260613-demo-data-cleanup'

function isLegacyUploadUrl(url) {
  const value = String(url || '')
  return (
    value.indexOf('/uploads/') >= 0 ||
    value.indexOf('/uploads/demo/') >= 0 ||
    value.indexOf('124.223.146.85') >= 0 ||
    value.indexOf('flask-fnnj') >= 0 ||
    value.indexOf('tcloudbase.com/uploads/') >= 0
  )
}

Component({
  properties: {
    product: {
      type: Object,
      value: {},
      observer(value) {
        this.prepareProduct(value || {})
      }
    }
  },
  data: {
    conditionText: '',
    campusText: '',
    coverImage: '',
    coverText: '闲置',
    coverFailed: false
  },
  lifetimes: {
    attached() {
      this.prepareProduct(this.data.product || {})
    }
  },
  methods: {
    prepareProduct(product) {
      const conditionMap = {
        new: '全新',
        like_new: '几乎全新',
        good: '成色良好',
        fair: '有使用痕迹'
      }
      const images = Array.isArray(product.images) ? product.images : []
      const title = product.title || '闲置好物'
      const rawImage = product.cover_image || images[0] || ''
      const imageMeta = isLegacyUploadUrl(rawImage)
        ? { url: DEFAULT_PRODUCT_IMAGE, legacy: true }
        : normalizeImageMeta(rawImage, 'product')
      if (imageMeta.url === DEFAULT_PRODUCT_IMAGE && rawImage) {
        console.warn('[product-card fallback]', IMAGE_GUARD_VERSION, product.id || '', title, rawImage)
      }
      this.setData({
        conditionText: conditionMap[product.condition] || '校内闲置',
        campusText: product.campus || (product.seller && product.seller.campus) || '校内',
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
      if (!id) return
      wx.navigateTo({ url: `/pages/product/detail/index?id=${id}` })
    }
  }
})
