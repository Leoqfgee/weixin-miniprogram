const PRODUCT_STATUS_TEXT = {
  draft: '草稿',
  pending_review: '待审核',
  on_sale: '在售',
  locked: '交易中',
  sold: '已售出',
  rejected: '已驳回',
  off_shelf: '已下架'
}

const ORDER_STATUS_TEXT = {
  pending_payment: '待付款',
  pending_delivery: '待发货',
  pending_receive: '待收货',
  pending_review: '待评价',
  completed: '已完成',
  closed: '已取消',
  refunding: '售后中',
  refunded: '已退款'
}

const REFUND_STATUS_TEXT = {
  pending: '待处理',
  refunding: '退款中',
  refunded: '已退款',
  rejected: '已拒绝',
  closed: '已关闭'
}

const CONDITION_TEXT = {
  new: '全新',
  like_new: '几乎全新',
  good: '成色良好',
  fair: '有使用痕迹'
}

const DELIVERY_TEXT = {
  offline_meetup: '校内面交',
  campus_pickup: '校园自提',
  campus_delivery: '校内送达',
  express: '快递邮寄'
}

function safeText(value, fallback = '暂无') {
  if (value === undefined || value === null) return fallback
  const text = String(value).trim()
  if (!text || text === 'undefined' || text === 'null' || text === '--' || text === '-') return fallback
  return text
}

function money(value) {
  const number = Number(value || 0)
  return `￥${number.toFixed(Number.isInteger(number) ? 0 : 2)}`
}

function pad(value) {
  return String(value).padStart(2, '0')
}

function asDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatDateTime(value) {
  const date = asDate(value)
  if (!date) return '暂无'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatShortDate(value) {
  const date = asDate(value)
  if (!date) return '暂无'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  if (day === today) return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (day === today - 24 * 60 * 60 * 1000) return '昨天'
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function productStatus(status) {
  return PRODUCT_STATUS_TEXT[status] || safeText(status, '在售')
}

function orderStatus(status) {
  return ORDER_STATUS_TEXT[status] || safeText(status, '待处理')
}

function refundStatus(status, group) {
  return REFUND_STATUS_TEXT[group] || REFUND_STATUS_TEXT[status] || safeText(status, '待处理')
}

function condition(value) {
  return CONDITION_TEXT[value] || safeText(value, '未填写')
}

function delivery(value) {
  return DELIVERY_TEXT[value] || safeText(value, '校内面交')
}

function orderStep(status) {
  if (status === 'refunded') return 4
  return { pending_payment: 0, pending_delivery: 1, pending_receive: 2, pending_review: 3, completed: 4, refunding: 2 }[status] || 0
}

function orderTip(order, role) {
  const status = order && order.status
  if (status === 'pending_payment') return '等待买家付款'
  if (status === 'pending_delivery') return role === 'seller' ? '买家已付款，待您发货' : '等待卖家发货'
  if (status === 'pending_receive') return role === 'seller' ? '等待买家确认收货' : '卖家已发货，待您收货'
  if (status === 'pending_review') return '交易完成，待评价'
  if (status === 'completed') return '订单已完成'
  if (status === 'refunding') return '订单售后处理中'
  if (status === 'refunded') return '订单已退款'
  if (status === 'closed') return '订单已取消'
  return orderStatus(status)
}

function buyerAction(order) {
  const status = order && order.status
  const actions = (order && order.allowed_actions) || {}
  if (status === 'pending_payment' || actions.can_pay) return '去付款'
  if (status === 'pending_delivery') return '联系卖家'
  if (status === 'pending_receive' || actions.can_confirm_receipt) return '确认收货'
  if (status === 'refunding' || status === 'refunded') return '查看售后'
  return '查看详情'
}

function sellerAction(order) {
  const status = order && order.status
  const actions = (order && order.allowed_actions) || {}
  if (status === 'pending_delivery' || actions.can_seller_deliver) return '去发货'
  if (status === 'refunding' || actions.can_agree_refund || actions.can_reject_refund) return '处理售后'
  return '查看详情'
}

module.exports = {
  PRODUCT_STATUS_TEXT,
  ORDER_STATUS_TEXT,
  REFUND_STATUS_TEXT,
  CONDITION_TEXT,
  DELIVERY_TEXT,
  safeText,
  money,
  formatDateTime,
  formatShortDate,
  productStatus,
  orderStatus,
  refundStatus,
  condition,
  delivery,
  orderStep,
  orderTip,
  buyerAction,
  sellerAction
}
