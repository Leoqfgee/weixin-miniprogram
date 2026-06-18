const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')

const STATUS_TIP = {
  pending: '请在规定时间内处理，超时将自动同意退款',
  refunding: '退款处理中',
  refunded: '退款已完成',
  rejected: '退款已拒绝',
  closed: '售后已关闭'
}

Page({
  data: {
    id: '',
    refund: null,
    loading: false
  },
  onLoad(options) {
    this.setData({ id: options.id || '' })
  },
  onShow() {
    if (!requireLogin()) return
    this.loadDetail()
  },
  onPullDownRefresh() {
    this.loadDetail()
    wx.stopPullDownRefresh()
  },
  loadDetail() {
    if (!this.data.id) {
      wx.showToast({ title: '售后单不存在', icon: 'none' })
      return
    }
    this.setData({ loading: true })
    api.get(`/refunds/${this.data.id}`, {}, { loading: true, loadingText: '加载售后' }).then((data) => {
      const group = data.status_group || ''
      data.status_tip = STATUS_TIP[group] || STATUS_TIP[data.status] || ''
      this.setData({ refund: data })
      refreshUnreadBadge()
    }).catch(() => {
      wx.showToast({ title: '售后详情加载失败，请重试', icon: 'none' })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },
  copyText(event) {
    const value = event.currentTarget.dataset.value
    if (value) wx.setClipboardData({ data: value })
  },
  previewEvidence(event) {
    const current = event.currentTarget.dataset.url
    const urls = (this.data.refund && this.data.refund.evidence_images) || []
    if (current && urls.length) {
      wx.previewImage({ current, urls })
    }
  },
  contactBuyer() {
    const refund = this.data.refund
    if (!refund || !refund.buyer || !refund.buyer.id) return
    const productId = refund.product && refund.product.id ? `&product_id=${refund.product.id}` : ''
    wx.navigateTo({ url: `/pages/message/chat/index?receiver_id=${refund.buyer.id}${productId}` })
  },
  agreeRefund() {
    wx.showModal({
      title: '同意退款',
      content: '确认同意该售后申请并处理退款吗？',
      confirmText: '同意退款',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/refunds/${this.data.id}/seller-handle`, {
          action: 'agree',
          reason: '卖家同意退款'
        }, { loading: true, loadingText: '处理中' }).then(() => {
          wx.showToast({ title: '已同意退款', icon: 'success' })
          this.loadDetail()
        })
      }
    })
  },
  refuseRefund() {
    wx.showModal({
      title: '拒绝退款',
      content: '请填写拒绝原因，原因会发送给买家。',
      editable: true,
      placeholderText: '请输入拒绝原因',
      confirmText: '确认拒绝',
      success: (res) => {
        if (!res.confirm) return
        const reason = (res.content || '').trim()
        if (!reason) {
          wx.showToast({ title: '请填写拒绝原因', icon: 'none' })
          return
        }
        wx.showModal({
          title: '确认拒绝退款',
          content: `拒绝原因：${reason}`,
          confirmText: '确认拒绝',
          success: (confirmRes) => {
            if (!confirmRes.confirm) return
            api.post(`/refunds/${this.data.id}/seller-handle`, {
              action: 'refuse',
              reason
            }, { loading: true, loadingText: '处理中' }).then(() => {
              wx.showToast({ title: '已拒绝退款', icon: 'success' })
              this.loadDetail()
            })
          }
        })
      }
    })
  },
  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack()
    } else {
      wx.navigateTo({ url: '/pages/refund/list/index?role=seller' })
    }
  }
})
