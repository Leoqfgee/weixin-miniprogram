const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')
const { safeText, formatMoney, formatDateTime, normalizeCampusText, orderStatusText, orderTip, conditionText, refundStatusText, refundReasonText } = require('../../../utils/format')

const DELIVERY_TEXT = { offline_meetup: '校内面交', campus_pickup: '校园自提', campus_delivery: '校内送达', express: '快递邮寄' }

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
  },
  onShow() {
    if (this.data.id) this.loadOrder()
  },
  loadOrder() {
    api.get(`/orders/${this.data.id}`, {}, { loading: true }).then((rawOrder) => {
      const order = Object.assign({}, rawOrder)
      if (order.delivery) {
        order.delivery.delivery_type_text = DELIVERY_TEXT[order.delivery.delivery_type] || order.delivery.delivery_type
        order.delivery.location_text = order.delivery.meet_location || order.delivery.pickup_location || order.delivery.campus_address || order.delivery.tracking_no || '\u6682\u65e0'
      }
      const role = order.current_role || ((order.allowed_actions && order.allowed_actions.can_seller_deliver) ? 'seller' : 'buyer')
      order.status_text = orderStatusText(order.status)
      order.status_tip = orderTip(order.status, role)
      order.display_amount = formatMoney(order.total_amount || order.pay_amount)
      order.display_time = formatDateTime(order.created_at || order.created_time)
      order.display_no = safeText(order.order_no, '\u6682\u65e0')
      order.contact_label = role === 'seller' ? '\u8054\u7cfb\u4e70\u5bb6' : '\u8054\u7cfb\u5356\u5bb6'
      order.items = (order.items || []).map((item) => Object.assign({}, item, {
        display_price: formatMoney(item.unit_price),
        product_snapshot: Object.assign({}, item.product_snapshot || {}, {
          display_title: safeText((item.product_snapshot || {}).title, '\u8ba2\u5355\u5546\u54c1'),
          display_condition: conditionText((item.product_snapshot || {}).condition || (item.product_snapshot || {}).condition_text)
        })
      }))
      if (order.refund) {
        order.refund = Object.assign({}, order.refund, {
          status_text: refundStatusText(order.refund.status_group || order.refund.status),
          display_reason: refundReasonText(order.refund.reason_text || order.refund.reason)
        })
      }
      order.product_snapshot = order.product_snapshot || ((order.items[0] || {}).product_snapshot || {})
      order.contact_user = Object.assign({}, order.contact_user || {}, {
        display_name: safeText(order.contact_user && order.contact_user.nickname, '\u6821\u56ed\u540c\u5b66'),
        display_campus: normalizeCampusText(order.contact_user && order.contact_user.campus, '\u672a\u586b\u5199')
      })
      this.setData({
        order,
        currentStep: this.getStepIndex(order.status),
        fundText: this.getFundText(order),
        actionMap: this.buildActionMap(order.allowed_actions)
      })
    })
  },
  buildActionMap(allowedActions) {
    return ((allowedActions && allowedActions.actions) || []).reduce((map, action) => {
      map[action] = true
      return map
    }, {})
  },
  getStepIndex(status) {
    return { pending_payment: 0, pending_delivery: 1, pending_receive: 2, pending_review: 3, completed: 4 }[status] || 0
  },
  getFundText(order) {
    if (order.escrow && order.escrow.status === 'holding') return '已付款，平台担保中（模拟）'
    if (order.escrow && order.escrow.status === 'settled') return '已结算给卖家（模拟）'
    if ((order.payment && order.payment.status === 'refunded') || order.status === 'refunded') return '已退款'
    return '未付款'
  },
  pay() {
    api.post('/payments/prepay', { order_id: this.data.id }, { loading: true })
      .then((data) => api.post('/payments/mock-confirm', { payment_id: data.payment.id, mock_result: 'success' }, { loading: true }))
      .then(() => this.loadOrder())
  },
  sellerCancel() {
    api.post(`/orders/${this.data.id}/seller-cancel`, { reason: '卖家取消交易' }, { loading: true }).then(() => this.loadOrder())
  },
  sellerDeliver() {
    wx.navigateTo({ url: `/pages/delivery/form/index?order_id=${this.data.id}` })
  },
  cancel() {
    api.post(`/orders/${this.data.id}/buyer-cancel`, {}, { loading: true }).then(() => this.loadOrder())
  },
  confirmReceipt() {
    api.post(`/deliveries/${this.data.id}/buyer-confirm`, {}, { loading: true }).then(() => this.loadOrder())
  },
  rejectReceive() {
    api.post(`/deliveries/${this.data.id}/buyer-reject`, { reason: '买家拒绝收货' }, { loading: true }).then(() => this.loadOrder())
  },
  review() {
    wx.navigateTo({ url: `/pages/review/apply/index?order_id=${this.data.id}` })
  },
  viewReview(event) {
    wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` })
  },
  applyRefund() {
    wx.navigateTo({ url: `/pages/refund/apply/index?order_id=${this.data.id}&amount=${this.data.order.pay_amount}` })
  },
  contactCounterparty() {
    const order = this.data.order || {}
    const user = order.contact_user || {}
    const snapshot = order.product_snapshot || {}
    if (!user.id) {
      wx.showToast({ title: '联系人信息不存在', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/message/chat/index?conversation_id=${order.conversation_id || ''}&receiver_id=${user.id}&product_id=${snapshot.product_id || order.product_id || ''}&order_id=${order.id}&product_title=${encodeURIComponent(snapshot.title || '')}&product_price=${snapshot.price || ''}&product_cover=${encodeURIComponent(snapshot.cover_image || '')}`
    })
  },
  viewProductSnapshot() {
    if (!this.data.order || !this.data.order.id) return
    wx.navigateTo({ url: `/pages/order/detail/index?id=${this.data.order.id}` })
  },
  viewRefund() {
    const refund = this.data.order && this.data.order.refund
    if (refund && refund.id) {
      wx.navigateTo({ url: `/pages/refund/detail/index?id=${refund.id}` })
      return
    }
    const role = (this.data.actionMap.agree_refund || this.data.actionMap.reject_refund || this.data.actionMap.seller_deliver) ? 'seller' : 'buyer'
    wx.navigateTo({ url: `/pages/refund/list/index?role=${role}&order_id=${this.data.id}` })
  },
  applyAppeal() {
    const refund = this.data.order && this.data.order.refund
    if (refund && refund.id) wx.navigateTo({ url: `/pages/appeal/apply/index?refund_id=${refund.id}` })
  }
})
