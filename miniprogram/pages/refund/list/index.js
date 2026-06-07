const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

Page({
  data: {
    refunds: [],
    isAdmin: false,
    orderId: '',
    role: '',
    partialAmount: ''
  },
  onLoad(options) {
    this.setData({
      orderId: options.order_id || '',
      role: options.role || ''
    })
  },
  onShow() {
    if (!requireLogin()) return
    this.setData({ isAdmin: hasRole('admin') })
    this.loadRefunds()
  },
  loadRefunds() {
    api.get(this.data.isAdmin ? '/admin/refunds' : '/refunds').then((data) => {
      let refunds = data.items || []
      if (this.data.orderId) {
        refunds = refunds.filter((item) => item.order_id === this.data.orderId || (item.order && item.order.id === this.data.orderId))
      }
      this.setData({ refunds })
    })
  },
  sellerHandle(event) {
    const id = event.currentTarget.dataset.id
    const result = event.currentTarget.dataset.result
    if (result === 'partial_refund') {
      this.openPartialRefund(id)
      return
    }
    const url = result === 'approved' ? `/refunds/${id}/seller-agree` : `/refunds/${id}/seller-reject`
    api.post(url, {
      reason: result === 'approved' ? '卖家同意售后' : '卖家拒绝售后'
    }, { loading: true }).then(() => this.loadRefunds())
  },
  openPartialRefund(id) {
    wx.showModal({
      title: '部分退款',
      editable: true,
      placeholderText: '输入最终退款金额',
      success: (res) => {
        if (!res.confirm) return
        const amount = Number(res.content)
        if (!amount || amount <= 0) {
          wx.showToast({ title: '请填写有效金额', icon: 'none' })
          return
        }
        api.post(`/refunds/${id}/seller-handle`, {
          result: 'partial_refund',
          final_refund_amount: amount,
          reason: '卖家提出部分退款'
        }, { loading: true }).then(() => this.loadRefunds())
      }
    })
  },
  arbitrate(event) {
    const id = event.currentTarget.dataset.id
    const result = event.currentTarget.dataset.result
    if (result === 'partial_refund') {
      wx.showModal({
        title: '平台部分退款',
        editable: true,
        placeholderText: '输入最终退款金额',
        success: (res) => {
          if (!res.confirm) return
          api.post(`/admin/refunds/${id}/arbitrate`, {
            result: 'partial_refund',
            final_refund_amount: Number(res.content),
            reason: '平台裁定部分退款'
          }, { loading: true }).then(() => this.loadRefunds())
        }
      })
      return
    }
    api.post(`/admin/refunds/${id}/arbitrate`, {
      result,
      reason: result === 'approved' ? '平台支持买家售后' : '平台支持卖家拒绝'
    }, { loading: true }).then(() => this.loadRefunds())
  }
})
