const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { orderStatus, formatDateTime, money, sellerAction, safeText } = require('../../../utils/format')

Page({
  data: { orders: [], statusIndex: 0, statusOptions: [{ label: '全部', value: '' }, { label: '待发货', value: 'pending_delivery' }, { label: '待收货', value: 'pending_receive' }, { label: '售后中', value: 'refunding' }, { label: '已完成', value: 'completed' }, { label: '已退款', value: 'refunded' }] },
  onShow() { if (requireLogin()) this.loadOrders() },
  selectStatus(event) { this.setData({ statusIndex: Number(event.currentTarget.dataset.index) }); this.loadOrders() },
  loadOrders() { const option = this.data.statusOptions[this.data.statusIndex]; const params = { role: 'seller', page: 1, page_size: 50 }; if (option.value) params.status = option.value; api.get('/orders', params, { loading: true }).then((data) => { const orders = (data.items || []).map((item) => { const snapshot = item.product_snapshot || ((item.items || [])[0] || {}).product_snapshot || {}; return Object.assign({}, item, { snapshot, status_text: orderStatus(item.status), price_text: money(item.total_amount), created_text: formatDateTime(item.created_at), party_name: safeText(item.buyer && item.buyer.nickname, '买家'), action_text: sellerAction(item) }) }); this.setData({ orders }) }) },
  goDetail(event) { wx.navigateTo({ url: `/pages/order/detail/index?id=${event.currentTarget.dataset.id}` }) },
  primaryAction(event) { const order = this.data.orders[Number(event.currentTarget.dataset.index)]; if (!order) return; if (order.status === 'pending_delivery' || order.allowed_actions.can_seller_deliver) return this.deliver({ currentTarget: { dataset: { id: order.id } } }); if (order.status === 'refunding' || order.allowed_actions.can_agree_refund || order.allowed_actions.can_reject_refund) return this.handleAfterSale({ currentTarget: { dataset: { id: order.id } } }); this.goDetail({ currentTarget: { dataset: { id: order.id } } }) },
  handleAfterSale(event) { wx.navigateTo({ url: `/pages/refund/list/index?role=seller&order_id=${event.currentTarget.dataset.id}` }) },
  deliver(event) { wx.navigateTo({ url: `/pages/delivery/form/index?order_id=${event.currentTarget.dataset.id}` }) },
  sellerCancel(event) { api.post(`/orders/${event.currentTarget.dataset.id}/seller-cancel`, { reason: '卖家取消交易' }, { loading: true }).then(() => { wx.showToast({ title: '已取消并退款', icon: 'success' }); this.loadOrders() }) }
})
