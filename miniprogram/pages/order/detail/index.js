const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    id: '',
    order: null,
    steps: [
      { key: 'pending_payment', text: '待付款' },
      { key: 'pending_delivery', text: '待交付' },
      { key: 'pending_receive', text: '待收货' },
      { key: 'pending_review', text: '待评价' },
      { key: 'completed', text: '完成' }
    ],
    currentStep: 0,
    fundText: '未付款'
  },
  onLoad(options) {
    requireLogin()
    this.setData({ id: options.id || '' })
    this.loadOrder()
  },
  loadOrder() {
    if (!this.data.id) return
    api.get(`/orders/${this.data.id}`, {}, { loading: true }).then((data) => {
      this.setData({
        order: data,
        currentStep: this.getStepIndex(data.status),
        fundText: this.getFundText(data)
      })
    })
  },
  getStepIndex(status) {
    const map = {
      pending_payment: 0,
      pending_delivery: 1,
      pending_receive: 2,
      pending_review: 3,
      completed: 4
    }
    return map[status] || 0
  },
  getFundText(order) {
    if (order.escrow && order.escrow.status === 'holding') return '已付款，平台担保中（模拟）'
    if (order.escrow && order.escrow.status === 'settled') return '已结算给卖家（模拟）'
    if ((order.payment && order.payment.status === 'refunded') || order.status === 'refunded') return '已退款'
    return '未付款'
  },
  pay() {
    api.post('/payments/prepay', { order_id: this.data.id }, { loading: true })
      .then((data) => api.post('/payments/mock-confirm', {
        payment_id: data.payment.id,
        mock_result: 'success'
      }, { loading: true }))
      .then(() => {
        wx.showToast({ title: '模拟微信支付成功', icon: 'success' })
        this.loadOrder()
      })
  },
  sellerCancel() {
    api.post(`/orders/${this.data.id}/seller-cancel`, { reason: '卖家取消交易' }, { loading: true }).then(() => {
      wx.showToast({ title: '已进入退款处理', icon: 'success' })
      this.loadOrder()
    })
  },
  sellerDeliver() {
    api.post(`/deliveries/${this.data.id}/seller-deliver`, {
      delivery_type: 'offline_meetup',
      meet_location: this.data.order.meet_location || '校内约定地点',
      delivery_note: '卖家已确认交付'
    }, { loading: true }).then(() => {
      wx.showToast({ title: '已确认交付', icon: 'success' })
      this.loadOrder()
    })
  },
  cancel() {
    api.post(`/orders/${this.data.id}/cancel`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已取消', icon: 'success' })
      this.loadOrder()
    })
  },
  confirmReceipt() {
    api.post(`/deliveries/${this.data.id}/buyer-confirm`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已确认收货', icon: 'success' })
      this.loadOrder()
    })
  },
  rejectReceive() {
    api.post(`/deliveries/${this.data.id}/buyer-reject`, { reason: '买家拒绝收货' }, { loading: true }).then(() => {
      wx.showToast({ title: '已进入售后', icon: 'success' })
      this.loadOrder()
    })
  },
  review() {
    wx.showModal({
      title: '订单评价',
      editable: true,
      placeholderText: '写一句评价',
      success: (res) => {
        if (!res.confirm) return
        api.post('/reviews', {
          order_id: this.data.id,
          rating: 5,
          content: res.content || '交易顺利'
        }, { loading: true }).then(() => {
          wx.showToast({ title: '评价成功', icon: 'success' })
          this.loadOrder()
        })
      }
    })
  },
  applyRefund() {
    wx.navigateTo({ url: `/pages/refund/apply/index?order_id=${this.data.id}&amount=${this.data.order.pay_amount}` })
  },
  applyAppeal() {
    if (!this.data.order.refund || !this.data.order.refund.id) {
      wx.showToast({ title: '暂无可介入的退款', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/appeal/apply/index?refund_id=${this.data.order.refund.id}` })
  }
})
