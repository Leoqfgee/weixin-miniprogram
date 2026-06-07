const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { ORDER_STATUS_TEXT } = require('../../../utils/constants')

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
      const orders = (data.items || []).map((item) => ({
        ...item,
        status_text: ORDER_STATUS_TEXT[item.status] || item.status,
        snapshot: item.product_snapshot || ((item.items || [])[0] || {}).product_snapshot || {}
      }))
      this.setData({ orders })
    })
  },
  goDetail(event) {
    wx.navigateTo({ url: `/pages/order/detail/index?id=${event.currentTarget.dataset.id}` })
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
