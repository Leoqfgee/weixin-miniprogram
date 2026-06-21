const PRODUCT_STATUS_TEXT = {
  draft: '草稿',
  pending_review: '待处理',
  on_sale: '在售',
  active: '在售',
  locked: '交易中',
  sold: '已售出',
  rejected: '未发现违规',
  off_shelf: '已下架',
  taken_down: '已下架',
  removed: '已下架'
}

const ORDER_STATUS_TEXT = {
  pending_payment: '待付款',
  pending_delivery: '待交付',
  pending_receive: '待收货',
  pending_review: '待评价',
  completed: '已完成',
  refunding: '售后中',
  refunded: '已退款',
  closed: '已取消'
}

const REFUND_STATUS_TEXT = {
  pending: '待处理',
  requested: '待处理',
  refunding: '退款中',
  seller_agreed: '退款中',
  refunded: '已退款',
  partial_refunded: '已退款',
  rejected: '已拒绝',
  seller_rejected: '已拒绝',
  closed: '已关闭'
}

const REPORT_STATUS_TEXT = {
  pending: '待处理',
  approved: '举报成立',
  rejected: '未发现违规',
  malicious: '恶意举报'
}

const CONDITION_TEXT = {
  new: '全新',
  like_new: '几乎全新',
  line_new: '几乎全新',
  good: '轻微使用痕迹',
  fair: '明显使用痕迹'
}

function safeText(value, fallback = '暂无') {
  if (value === undefined || value === null) return fallback
  const text = String(value).trim()
  if (!text || text === 'undefined' || text === 'null' || text === '--' || text === '-') return fallback
  return text
}

function formatMoney(value) {
  if (value === undefined || value === null || value === '') return '¥--'
  const number = Number(String(value).replace(/[¥￥\s]/g, ''))
  if (Number.isNaN(number)) return '¥--'
  return `¥${number.toFixed(Number.isInteger(number) ? 0 : 2)}`
}

function toDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function pad(value) {
  return String(value).padStart(2, '0')
}

function formatDateTime(value) {
  const date = toDate(value)
  if (!date) return '暂无'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatChatTime(value) {
  const date = toDate(value)
  if (!date) return '暂无'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const thatDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  if (thatDay === today) return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (thatDay === today - 86400000) return '昨天'
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function normalizeCampusText(value, fallback = '校内') {
  const text = safeText(value, '')
  if (text === '主校区') return '东校区'
  if (text === '东校区' || text === '西校区') return text
  return fallback
}

function normalizeKey(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function productStatusText(status) {
  const key = normalizeKey(status)
  const map = Object.assign({}, PRODUCT_STATUS_TEXT, {
    onsale: '在售',
    sale: '在售',
    selling: '在售',
    offsale: '已下架',
    sold_out: '已售出'
  })
  return map[key] || '处理中'
}

function orderStatusText(status) {
  const key = normalizeKey(status)
  const map = Object.assign({}, ORDER_STATUS_TEXT, {
    paid: '已付款',
    delivered: '已发货',
    shipped: '已发货',
    cancel: '已取消',
    cancelled: '已取消',
    complete: '已完成',
    after_sale: '售后中',
    aftersale: '售后中'
  })
  return map[key] || '订单处理中'
}

function refundStatusText(status) {
  const key = normalizeKey(status)
  return REFUND_STATUS_TEXT[key] || '待处理'
}

function reportStatusText(status) {
  const key = normalizeKey(status)
  return REPORT_STATUS_TEXT[key] || '待处理'
}

function refundReasonText(value) {
  const key = normalizeKey(value)
  const map = {
    good: '商品与描述不符',
    quality: '商品质量问题',
    damaged: '商品有破损',
    not_as_described: '商品与描述不符',
    mismatch: '商品与描述不符',
    fake: '疑似非正品',
    dislike: '不喜欢了',
    change_mind: '不想要了',
    no_need: '不需要了',
    received: '买家拒收/收货问题',
    has_defect: '商品有瑕疵',
    defect: '商品有瑕疵',
    broken: '商品有破损',
    wrong_item: '商品与描述不符',
    other: '其他原因'
  }
  return map[key] || safeText(value, '未填写')
}

function conditionText(condition) {
  const raw = safeText(condition, '')
  const key = normalizeKey(raw)
  if (CONDITION_TEXT[key]) return CONDITION_TEXT[key]
  if (/^[a-z_\-\s]+$/.test(raw)) return '成色未填写'
  return raw || '成色未填写'
}

function orderTip(status, role) {
  const seller = role === 'seller'
  const map = {
    pending_payment: '等待买家付款',
    pending_delivery: seller ? '买家已付款，待您交付' : '等待卖家交付',
    pending_receive: seller ? '已交付，等待买家收货' : '卖家已交付，请确认收货',
    pending_review: '交易完成，等待评价',
    completed: '订单已完成',
    refunding: '订单正在售后处理中',
    refunded: '订单已退款',
    closed: '订单已取消'
  }
  return map[status] || '订单处理中'
}

module.exports = {
  PRODUCT_STATUS_TEXT,
  ORDER_STATUS_TEXT,
  REFUND_STATUS_TEXT,
  REPORT_STATUS_TEXT,
  CONDITION_TEXT,
  safeText,
  formatMoney,
  formatDateTime,
  formatChatTime,
  normalizeCampusText,
  productStatusText,
  orderStatusText,
  refundStatusText,
  reportStatusText,
  refundReasonText,
  conditionText,
  orderTip
}
