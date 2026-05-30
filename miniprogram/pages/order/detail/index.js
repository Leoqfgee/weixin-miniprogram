const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

const DELIVERY_TYPE_TEXT = {
  offline_meetup: '校内面交',
  campus_pickup: '校园自提',
  campus_delivery: '校内送达',
  express: '快递邮寄'
}

const REFUND_STATUS_TEXT = {
  requested: '买家已申请',
  seller_agreed: '卖家已同意',
  seller_rejected: '卖家已拒绝',
  waiting_return: '等待退回',
  return_delivered: '买家已退回',
  refunded: '已退款',
  closed: '已关闭'
}

const APPEAL_STATUS_TEXT = {
  pending: '平台介入中',
  approved: '支持买家',
  rejected: '支持卖家',
  partial_refund: '部分退款',
  closed: '已关闭'
}

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
      const order = this.enrichOrder(data)
      this.setData({
        order,
        currentStep: this.getStepIndex(order.status),
        fundText: this.getFundText(order),
        actionMap: this.buildActionMap(order.allowed_actions)
      })
    })
  },
  enrichOrder(order) {
    const delivery = order.delivery || null
    if (delivery) {
      delivery.delivery_type_text = DELIVERY_TYPE_TEXT[delivery.delivery_type] || delivery.delivery_type
      delivery.location_text = delivery.meet_location || delivery.pickup_location || delivery.campus_address || delivery.tracking_no || delivery.delivery_note || '暂无'
    }
    if (order.refund) {
      order.refund.status_text = REFUND_STATUS_TEXT[order.refund.status] || order.refund.status
    }
    if (order.appeal) {
      order.appeal.status_text = APPEAL_STATUS_TEXT[order.appeal.status] || order.appeal.status
    }
    return order
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
    wx.navigateTo({ url: `/pages/delivery/form/index?order_id=${this.data.id}` })
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
