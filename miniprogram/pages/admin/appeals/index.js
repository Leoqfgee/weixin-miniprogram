const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

Page({
  data: {
    status: 'pending',
    appeals: []
  },
  onLoad() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可访问', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadAppeals()
  },
  loadAppeals() {
    api.get('/admin/appeals', { status: this.data.status, page: 1, page_size: 30 }, { loading: true }).then((data) => {
      this.setData({ appeals: data.items || [] })
    })
  },
  setPending() {
    this.setData({ status: 'pending' })
    this.loadAppeals()
  },
  setAll() {
    this.setData({ status: '' })
    this.loadAppeals()
  },
  arbitrate(event) {
    const id = event.currentTarget.dataset.id
    const action = event.currentTarget.dataset.action
    const reasonMap = {
      refund: '管理员支持买家退款',
      reject_refund: '管理员支持卖家，驳回退款',
      partial_refund: '管理员判定部分退款',
      close: '管理员关闭申诉'
    }
    wx.showModal({
      title: '确认仲裁',
      content: reasonMap[action],
      success: (res) => {
        if (!res.confirm) return
        api.post(`/admin/appeals/${id}/arbitrate`, {
          force_action: action,
          reason: reasonMap[action]
        }, { loading: true }).then(() => {
          wx.showToast({ title: '已处理', icon: 'success' })
          this.loadAppeals()
        })
      }
    })
  }
})
