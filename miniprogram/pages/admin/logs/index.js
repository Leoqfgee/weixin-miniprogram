const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

Page({
  data: {
    stats: null,
    logs: []
  },
  onLoad() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可访问', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadData()
  },
  loadData() {
    api.get('/admin/stats').then((stats) => this.setData({ stats }))
    api.get('/admin/operation-logs', { page: 1, page_size: 20 }).then((data) => {
      this.setData({ logs: data.items || [] })
    })
  }
})
