const PRODUCT_STATUS_TEXT = {
  draft: '\u8349\u7a3f',
  pending_review: '\u5f85\u5ba1\u6838',
  on_sale: '\u5728\u552e',
  locked: '\u4ea4\u6613\u4e2d',
  sold: '\u5df2\u552e\u51fa',
  rejected: '\u672a\u901a\u8fc7',
  off_shelf: '\u5df2\u4e0b\u67b6'
}

const ORDER_STATUS_TEXT = {
  pending_payment: '\u5f85\u4ed8\u6b3e',
  pending_delivery: '\u5f85\u53d1\u8d27',
  pending_receive: '\u5f85\u6536\u8d27',
  pending_review: '\u5f85\u8bc4\u4ef7',
  completed: '\u5df2\u5b8c\u6210',
  refunding: '\u552e\u540e\u4e2d',
  refunded: '\u5df2\u9000\u6b3e',
  closed: '\u5df2\u53d6\u6d88'
}

const REFUND_STATUS_TEXT = {
  pending: '\u5f85\u5904\u7406',
  refunding: '\u9000\u6b3e\u4e2d',
  refunded: '\u5df2\u9000\u6b3e',
  rejected: '\u5df2\u62d2\u7edd',
  closed: '\u5df2\u5173\u95ed'
}

const CONDITION_TEXT = {
  new: '\u5168\u65b0',
  like_new: '\u51e0\u4e4e\u5168\u65b0',
  good: '\u8f7b\u5fae\u4f7f\u7528\u75d5\u8ff9',
  fair: '\u660e\u663e\u4f7f\u7528\u75d5\u8ff9'
}

function safeText(value, fallback = '\u6682\u65e0') {
  if (value === undefined || value === null) return fallback
  const text = String(value).trim()
  if (!text || text === 'undefined' || text === 'null' || text === '--' || text === '-') return fallback
  return text
}

function formatMoney(value) {
  const number = Number(value || 0)
  return `\uffe5${number.toFixed(Number.isInteger(number) ? 0 : 2)}`
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
  if (!date) return '\u6682\u65e0'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatChatTime(value) {
  const date = toDate(value)
  if (!date) return '\u6682\u65e0'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const thatDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  if (thatDay === today) return `\u4eca\u5929 ${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (thatDay === today - 86400000) return '\u6628\u5929'
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function productStatusText(status) {
  return PRODUCT_STATUS_TEXT[status] || PRODUCT_STATUS_TEXT.on_sale
}

function orderStatusText(status) {
  return ORDER_STATUS_TEXT[status] || safeText(status, '\u5f85\u5904\u7406')
}

function refundStatusText(status) {
  return REFUND_STATUS_TEXT[status] || safeText(status, '\u5f85\u5904\u7406')
}

function conditionText(condition) {
  return CONDITION_TEXT[condition] || '\u6210\u8272\u672a\u586b\u5199'
}

function orderTip(status, role) {
  const seller = role === 'seller'
  const map = {
    pending_payment: '\u7b49\u5f85\u4e70\u5bb6\u4ed8\u6b3e',
    pending_delivery: seller ? '\u4e70\u5bb6\u5df2\u4ed8\u6b3e\uff0c\u5f85\u60a8\u53d1\u8d27' : '\u7b49\u5f85\u5356\u5bb6\u53d1\u8d27',
    pending_receive: seller ? '\u5df2\u53d1\u8d27\uff0c\u7b49\u5f85\u4e70\u5bb6\u6536\u8d27' : '\u5356\u5bb6\u5df2\u53d1\u8d27\uff0c\u8bf7\u786e\u8ba4\u6536\u8d27',
    pending_review: '\u4ea4\u6613\u5b8c\u6210\uff0c\u7b49\u5f85\u8bc4\u4ef7',
    completed: '\u8ba2\u5355\u5df2\u5b8c\u6210',
    refunding: '\u8ba2\u5355\u6b63\u5728\u552e\u540e\u5904\u7406\u4e2d',
    refunded: '\u8ba2\u5355\u5df2\u9000\u6b3e',
    closed: '\u8ba2\u5355\u5df2\u53d6\u6d88'
  }
  return map[status] || '\u8ba2\u5355\u5904\u7406\u4e2d'
}

module.exports = {
  PRODUCT_STATUS_TEXT,
  ORDER_STATUS_TEXT,
  REFUND_STATUS_TEXT,
  CONDITION_TEXT,
  safeText,
  formatMoney,
  formatDateTime,
  formatChatTime,
  productStatusText,
  orderStatusText,
  refundStatusText,
  conditionText,
  orderTip
}
