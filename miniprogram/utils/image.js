const DEFAULT_PRODUCT_IMAGE = '/assets/images/default-product.png'
const DEFAULT_AVATAR_IMAGE = '/assets/tabbar/mine.png'
const COS_BASE_URL = 'https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com'

function defaultImage(type) {
  return type === 'avatar' ? DEFAULT_AVATAR_IMAGE : DEFAULT_PRODUCT_IMAGE
}

function normalizeImageMeta(url, type) {
  const fallback = defaultImage(type)
  const value = String(url || '').trim()
  if (!value) return { url: fallback, legacy: false }
  if (value.indexOf(COS_BASE_URL) === 0) return { url: value, legacy: false }
  if (value.indexOf('/uploads/demo/') === 0) return { url: fallback, legacy: true }
  if (value.indexOf('124.223.146.85') >= 0) return { url: fallback, legacy: true }
  if (value.indexOf('/uploads/') === 0) return { url: fallback, legacy: true }
  if (value.indexOf('flask-fnnj') >= 0 && value.indexOf('/uploads/') >= 0) return { url: fallback, legacy: true }
  if (value.indexOf('tcloudbase.com/uploads/') >= 0) return { url: fallback, legacy: true }
  if (value.indexOf('http://') === 0) return { url: fallback, legacy: true }
  return { url: value, legacy: false }
}

function normalizeImageUrl(url, type) {
  return normalizeImageMeta(url, type).url
}

function normalizeImageList(urls, type) {
  return (Array.isArray(urls) ? urls : []).map((item) => normalizeImageUrl(item, type))
}

module.exports = {
  COS_BASE_URL,
  DEFAULT_PRODUCT_IMAGE,
  DEFAULT_AVATAR_IMAGE,
  defaultImage,
  normalizeImageMeta,
  normalizeImageUrl,
  normalizeImageList
}
