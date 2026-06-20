const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { orderStatus, formatDateTime, money, buyerAction, safeText } = require('../../../utils/format')

Page({
  data: { orders: [], statusIndex: 0, statusOptions: [{ label: '全部', value: '' }, { label: '待付款', value: 'pending_payment' }, { label: '待发货', value: 'pending_delivery' }, { label: '待收货', value: 'pending_receive' }, { label: '售后中', value: 'refunding' }, { label: '已完成', value: 'completed' }] },
  onShow() { if (requireLogin()) this.loadOrders() },
  selectStatus(event) { this.setData({ statusIndex: Number(event.currentTarget.dataset.index) }); this.loadOrders() },
  loadOrders() { const option = this.data.statusOptions[this.data.statusIndex]; const params = { role: 'buyer', page: 1, page_size: 50 }; if (option.value) params.status = option.value; api.get('/orders', params, { loading: true }).then((data) => { const orders = (data.items || []).map((item) => { const snapshot = item.product_snapshot || ((item.items || [])[0] || {}).product_snapshot || {}; return Object.assign({}, item, { snapshot, status_text: orderStatus(item.status), price_text: money(item.total_amount), created_text: formatDateTime(item.created_at), party_name: safeText(item.seller && item.seller.nickname, '卖家'), action_text: buyerAction(item) }) }); this.setData({ orders }) }) },
  goDetail(event) { wx.navigateTo({ url: `/pages/order/detail/index?id=${event.currentTarget.dataset.id}` }) },
  primaryAction(event) { const order = this.data.orders[Number(event.currentTarget.dataset.index)]; if (!order) return; if (order.status === 'pending_payment' || order.allowed_actions.can_pay) return this.pay({ currentTarget: { dataset: { id: order.id } } }); if (order.status === 'pending_receive' || order.allowed_actions.can_confirm_receipt) return this.confirmReceive({ currentTarget: { dataset: { id: order.id } } }); if (order.status === 'refunding' || order.status === 'refunded') return wx.navigateTo({ url: `/pages/refund/list/index?role=buyer&order_id=${order.id}` }); this.goDetail({ currentTarget: { dataset: { id: order.id } } }) },
  applyAfterSale(event) { const id = event.currentTarget.dataset.id; const amount = event.currentTarget.dataset.amount || ''; wx.navigateTo({ url: `/pages/refund/apply/index?order_id=${id}&amount=${amount}` }) },
  pay(event) { const id = event.currentTarget.dataset.id; api.post('/payments/prepay', { order_id: id }, { loading: true }).then((data) => api.post('/payments/mock-confirm', { payment_id: data.payment.id, mock_result: 'success' }, { loading: true })).then(() => { wx.showToast({ title: '支付成功', icon: 'success' }); this.loadOrders() }) },
  confirmReceive(event) { api.post(`/deliveries/${event.currentTarget.dataset.id}/buyer-confirm`, {}, { loading: true }).then(() => { wx.showToast({ title: '已确认收货', icon: 'success' }); this.loadOrders() }) }
})
