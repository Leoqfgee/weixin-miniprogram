const { requireLogin, hasRole } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    products: []
  },
  onLoad() {
    if (!requireLogin()) {
      return
    }
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可访问', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadPending()
  },
  loadPending() {
    api.get('/admin/products', { status: 'pending_review', page: 1, page_size: 50 }, { loading: true })
      .then((data) => {
        this.setData({ products: data.items || [] })
      })
  },
  audit(event) {
    const id = event.currentTarget.dataset.id
    const result = event.currentTarget.dataset.result
    const text = result === 'approved' ? '通过' : '驳回'
    wx.showModal({
      title: `确认${text}`,
      content: result === 'approved' ? '审核通过后商品会展示到首页。' : '驳回后卖家可修改后重新提交。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/admin/products/${id}/audit`, {
          result,
          reason: result === 'approved' ? '小程序端审核通过' : '信息不完整，请修改后重新提交'
        }, { loading: true }).then(() => {
          wx.showToast({ title: `已${text}`, icon: 'success' })
          this.loadPending()
        })
      }
    })
  }
})
