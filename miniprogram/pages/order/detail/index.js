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
    fundText: '未付款',
    actionMap: {}
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
        fundText: this.getFundText(data),
        actionMap: this.buildActionMap(data.allowed_actions)
      })
    })
  },
  buildActionMap(allowedActions) {
    const actions = (allowedActions && allowedActions.actions) || []
    return actions.reduce((map, action) => {
      map[action] = true
      return map
    }, {})
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
    wx.showModal({
      title: '确认交付',
      editable: true,
      placeholderText: '填写面交地点或交付说明',
      success: (res) => {
        if (!res.confirm) return
        const content = (res.content || '').trim()
        if (!content) {
          wx.showToast({ title: '请填写交付地点或说明', icon: 'none' })
          return
        }
        api.post(`/deliveries/${this.data.id}/seller-deliver`, {
          delivery_type: 'offline_meetup',
          meet_location: content,
          delivery_note: content
        }, { loading: true }).then(() => {
          wx.showToast({ title: '已确认交付', icon: 'success' })
          this.loadOrder()
        })
      }
    })
  },
  cancel() {
    api.post(`/orders/${this.data.id}/buyer-cancel`, {}, { loading: true }).then(() => {
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
  viewRefund() {
    const refund = this.data.order && this.data.order.refund
    if (!refund) {
      wx.showToast({ title: '暂无售后记录', icon: 'none' })
      return
    }
    wx.showModal({
      title: '售后进度',
      content: `退款状态：${refund.status || '待处理'}\n原因：${refund.reason || '无'}\n卖家处理：${refund.seller_result || '待处理'}`,
      showCancel: false
    })
  },
  applyAppeal() {
    if (!this.data.order.refund || !this.data.order.refund.id) {
      wx.showToast({ title: '暂无可介入的退款', icon: 'none' })
      return
    }
    if (this.data.order.refund.status !== 'seller_rejected') {
      wx.showToast({ title: '卖家拒绝后才能介入', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/appeal/apply/index?refund_id=${this.data.order.refund.id}` })
  }
})
