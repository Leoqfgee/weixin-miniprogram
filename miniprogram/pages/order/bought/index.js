const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { ORDER_STATUS_TEXT } = require('../../../utils/constants')

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
      const orders = (data.items || []).map((item) => ({
        ...item,
        status_text: ORDER_STATUS_TEXT[item.status] || item.status,
        status_note: item.status === 'closed' ? '订单已取消，通常是主动取消或超时未支付' : '',
        snapshot: item.product_snapshot || ((item.items || [])[0] || {}).product_snapshot || {}
      }))
      this.setData({ orders })
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
