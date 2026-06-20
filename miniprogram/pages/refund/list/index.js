const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')
const { safeText, formatMoney, formatDateTime, refundStatusText } = require('../../../utils/format')

const TABS = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '退款中', value: 'refunding' },
  { label: '已退款', value: 'refunded' },
  { label: '已拒绝', value: 'rejected' },
  { label: '已关闭', value: 'closed' }
]

const ROLE_TABS = [
  { label: '我买的', value: 'buyer' },
  { label: '我卖的', value: 'seller' }
]

const ADMIN_ROLE_TABS = [
  { label: '买家申请', value: 'buyer' },
  { label: '卖家处理', value: 'seller' }
]


function normalizeRefund(item, role) {
  const product = item.product || {}
  const counterparty = item.counterparty || {}
  return Object.assign({}, item, {
    status_text: refundStatusText(item.status_group || item.status),
    display_amount: formatMoney(item.request_amount || item.amount),
    display_time: formatDateTime(item.created_at || item.apply_time),
    display_product_title: safeText(product.title, '\u552e\u540e\u5546\u54c1'),
    display_reason: safeText(item.reason_text || item.reason, '\u672a\u586b\u5199'),
    counterparty: Object.assign({}, counterparty, { display_name: safeText(counterparty.nickname, '\u6821\u56ed\u540c\u5b66') }),
    counterparty_label: item.counterparty_label || (role === 'buyer' ? '\u5356\u5bb6' : '\u4e70\u5bb6')
  })
}

Page({
  data: {
    roleTabs: ROLE_TABS,
    tabs: TABS,
    activeRoleIndex: 0,
    activeTab: 0,
    refunds: [],
    role: 'buyer',
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
    const role = options.role || 'buyer'
    this.setData({
      role,
      activeRoleIndex: role === 'seller' ? 1 : 0,
      orderId: options.order_id || ''
    })
  },
  onShow() {
    if (!requireLogin()) return
    const isAdmin = hasRole('admin')
    this.setData({ isAdmin, roleTabs: isAdmin ? ADMIN_ROLE_TABS : ROLE_TABS })
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
  selectRole(event) {
    const index = Number(event.currentTarget.dataset.index)
    const role = this.data.roleTabs[index] ? this.data.roleTabs[index].value : 'buyer'
    this.setData({ activeRoleIndex: index, role, activeTab: 0 })
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
      const mappedItems = items.map((item) => normalizeRefund(item, this.data.role))
      const refunds = reset ? mappedItems : this.data.refunds.concat(mappedItems)
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
