const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { ORDER_STATUS_TEXT } = require('../../../utils/constants')
const { safeText, formatMoney, formatDateTime, orderStatusText } = require('../../../utils/format')


function getActionKey(item) {
  if ('buyer' === 'buyer') {
    if (item.status === 'pending_payment' || (item.allowed_actions && item.allowed_actions.can_pay)) return 'pay'
    if (item.status === 'pending_delivery') return 'contact_seller'
    if (item.status === 'pending_receive' || (item.allowed_actions && item.allowed_actions.can_confirm_receipt)) return 'confirm'
    if (item.status === 'refunding' || item.status === 'refunded') return 'refund'
    return 'detail'
  }
  if (item.status === 'pending_delivery' || (item.allowed_actions && item.allowed_actions.can_seller_deliver)) return 'deliver'
  if (item.status === 'refunding' || (item.allowed_actions && (item.allowed_actions.can_agree_refund || item.allowed_actions.can_reject_refund))) return 'refund'
  return 'detail'
}

function normalizeOrder(item) {
  const snapshot = item.product_snapshot || ((item.items || [])[0] || {}).product_snapshot || {}
  const other = 'buyer' === 'buyer' ? (item.seller || {}) : (item.buyer || {})
  return Object.assign({}, item, {
    snapshot,
    display_title: safeText(snapshot.title || item.title, '\u8ba2\u5355\u5546\u54c1'),
    display_amount: formatMoney(item.total_amount || item.pay_amount || snapshot.price),
    display_status: orderStatusText(item.status),
    display_time: formatDateTime(item.created_at || item.created_time),
    counterparty_label: 'buyer' === 'buyer' ? '\u5356\u5bb6' : '\u4e70\u5bb6',
    counterparty_name: safeText(other.nickname, '\u6821\u56ed\u540c\u5b66'),
    action_key: getActionKey(item)
  })
}

Page({
  data: {
    orders: [],
    statusIndex: 0,
    statusOptions: [
      { label: '全部', value: '' },
      { label: '待付款', value: 'pending_payment' },
      { label: '待交付', value: 'pending_delivery' },
      { label: '待收货', value: 'pending_receive' },
      { label: '待评价', value: 'pending_review' },
      { label: '已完成', value: 'completed' },
      { label: '售后中', value: 'refunding' },
      { label: '已退款', value: 'refunded' },
      { label: '已取消', value: 'closed' }
    ]
  },
  onShow() {
    if (requireLogin()) this.loadOrders()
  },
  selectStatus(event) {
    this.setData({ statusIndex: Number(event.currentTarget.dataset.index) })
    this.loadOrders()
  },
  loadOrders() {
    const option = this.data.statusOptions[this.data.statusIndex]
    const params = { role: 'buyer', page: 1, page_size: 50 }
    if (option.value) params.status = option.value
    api.get('/orders', params, { loading: true }).then((data) => {
      this.setData({ orders: (data.items || []).map(normalizeOrder) })
    })
  },
  goDetail(event) {
    wx.navigateTo({ url: `/pages/order/detail/index?id=${event.currentTarget.dataset.id}` })
  },
  applyAfterSale(event) {
    const id = event.currentTarget.dataset.id
    const amount = event.currentTarget.dataset.amount || ''
    wx.navigateTo({ url: `/pages/refund/apply/index?order_id=${id}&amount=${amount}` })
  },
  pay(event) {
    const id = event.currentTarget.dataset.id
    api.post('/payments/prepay', { order_id: id }, { loading: true })
      .then((data) => api.post('/payments/mock-confirm', { payment_id: data.payment.id, mock_result: 'success' }, { loading: true }))
      .then(() => {
        wx.showToast({ title: '支付成功', icon: 'success' })
        this.loadOrders()
      })
  },
  confirmReceive(event) {
    api.post(`/deliveries/${event.currentTarget.dataset.id}/buyer-confirm`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已确认收货', icon: 'success' })
      this.loadOrders()
    })
  }
})
