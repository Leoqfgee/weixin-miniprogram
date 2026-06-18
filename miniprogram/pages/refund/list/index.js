const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')

const TABS = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '退款中', value: 'refunding' },
  { label: '已退款', value: 'refunded' },
  { label: '已拒绝', value: 'rejected' }
]

Page({
  data: {
    tabs: TABS,
    activeTab: 0,
    refunds: [],
    role: 'seller',
    orderId: '',
    isAdmin: false,
    page: 1,
    pageSize: 10,
    total: 0,
    loading: false,
    loadError: false,
    finished: false,
    pendingCount: 0
  },
  onLoad(options) {
    this.setData({
      role: options.role || 'seller',
      orderId: options.order_id || ''
    })
  },
  onShow() {
    if (!requireLogin()) return
    this.setData({ isAdmin: hasRole('admin') })
    this.refreshList()
  },
  onPullDownRefresh() {
    this.refreshList().finally(() => wx.stopPullDownRefresh())
  },
  onReachBottom() {
    if (!this.data.finished && !this.data.loading) {
      this.loadRefunds(false)
    }
  },
  selectTab(event) {
    this.setData({ activeTab: Number(event.currentTarget.dataset.index) })
    this.refreshList()
  },
  refreshList() {
    this.setData({ page: 1, refunds: [], finished: false, loadError: false })
    return this.loadRefunds(true)
  },
  loadRefunds(reset) {
    const tab = this.data.tabs[this.data.activeTab]
    const params = {
      role: this.data.role,
      page: this.data.page,
      page_size: this.data.pageSize
    }
    if (tab.value) params.status = tab.value
    if (this.data.orderId) params.order_id = this.data.orderId
    const url = this.data.isAdmin ? '/admin/refunds' : '/refunds'
    this.setData({ loading: true, loadError: false })
    return api.get(url, params, { loading: reset, loadingText: '加载售后' }).then((data) => {
      const items = data.items || []
      const pagination = data.pagination || {}
      const refunds = reset ? items : this.data.refunds.concat(items)
      const total = Number(pagination.total || refunds.length)
      this.setData({
        refunds,
        total,
        page: this.data.page + 1,
        finished: refunds.length >= total || items.length < this.data.pageSize,
        pendingCount: refunds.filter((item) => item.status_group === 'pending').length
      })
      refreshUnreadBadge()
    }).catch(() => {
      this.setData({ loadError: true })
      wx.showToast({ title: '售后列表加载失败，请下拉重试', icon: 'none' })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },
  goDetail(event) {
    const id = event.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/refund/detail/index?id=${id}` })
  },
  copyNo(event) {
    const no = event.currentTarget.dataset.no
    if (!no) return
    wx.setClipboardData({ data: no })
  },
  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack()
    } else {
      wx.switchTab({ url: '/pages/mine/index/index' })
    }
  }
})
