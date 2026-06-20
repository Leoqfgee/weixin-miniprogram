const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { ORDER_STATUS_TEXT } = require('../../../utils/constants')
const { safeText, formatMoney, formatDateTime, orderStatusText } = require('../../../utils/format')


function getActionKey(item) {
  if ('seller' === 'buyer') {
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
  const other = 'seller' === 'buyer' ? (item.seller || {}) : (item.buyer || {})
  return Object.assign({}, item, {
    snapshot,
    display_title: safeText(snapshot.title || item.title, '\u8ba2\u5355\u5546\u54c1'),
    display_amount: formatMoney(item.total_amount || item.pay_amount || snapshot.price),
    display_status: orderStatusText(item.status),
    display_time: formatDateTime(item.created_at || item.created_time),
    counterparty_label: 'seller' === 'buyer' ? '\u5356\u5bb6' : '\u4e70\u5bb6',
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
      { label: '待交付', value: 'pending_delivery' },
      { label: '待收货', value: 'pending_receive' },
      { label: '待评价', value: 'pending_review' },
      { label: '已完成', value: 'completed' },
      { label: '售后中', value: 'refunding' },
      { label: '已退款', value: 'refunded' }
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
    const params = { role: 'seller', page: 1, page_size: 50 }
    if (option.value) params.status = option.value
    api.get('/orders', params, { loading: true }).then((data) => {
      this.setData({ orders: (data.items || []).map(normalizeOrder) })
    })
  },
  goDetail(event) {
    wx.navigateTo({ url: `/pages/order/detail/index?id=${event.currentTarget.dataset.id}` })
  },
  handleAfterSale(event) {
    wx.navigateTo({ url: `/pages/refund/list/index?role=seller&order_id=${event.currentTarget.dataset.id}` })
  },
  deliver(event) {
    wx.navigateTo({ url: `/pages/delivery/form/index?order_id=${event.currentTarget.dataset.id}` })
  },
  sellerCancel(event) {
    api.post(`/orders/${event.currentTarget.dataset.id}/seller-cancel`, { reason: '卖家取消交易' }, { loading: true }).then(() => {
      wx.showToast({ title: '已取消并退款', icon: 'success' })
      this.loadOrders()
    })
  }
})
