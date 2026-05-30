const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

Page({
  data: {
    refunds: [],
    isAdmin: false
  },
  onShow() {
    if (!requireLogin()) return
    this.setData({ isAdmin: hasRole('admin') })
    this.loadRefunds()
  },
  loadRefunds() {
    api.get(this.data.isAdmin ? '/admin/refunds' : '/refunds').then((data) => {
      this.setData({ refunds: data.items || [] })
    })
  },
  sellerHandle(event) {
    const id = event.currentTarget.dataset.id
    const result = event.currentTarget.dataset.result
    const url = result === 'approved' ? `/refunds/${id}/seller-agree` : `/refunds/${id}/seller-reject`
    api.post(url, {
      reason: result === 'approved' ? '卖家同意退款' : '卖家拒绝退款'
    }, { loading: true }).then(() => this.loadRefunds())
  },
  arbitrate(event) {
    const id = event.currentTarget.dataset.id
    const result = event.currentTarget.dataset.result
    api.post(`/admin/refunds/${id}/arbitrate`, {
      result,
      reason: result === 'approved' ? '平台仲裁通过' : '平台仲裁驳回'
    }, { loading: true }).then(() => this.loadRefunds())
  }
})
