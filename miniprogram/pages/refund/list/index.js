const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')
const { refundStatus, formatDateTime, money, safeText } = require('../../../utils/format')

const TABS = [{ label: '全部', value: '' }, { label: '待处理', value: 'pending' }, { label: '退款中', value: 'refunding' }, { label: '已退款', value: 'refunded' }, { label: '已拒绝', value: 'rejected' }]
const ROLE_TABS = [{ label: '我买的', value: 'buyer' }, { label: '我卖的', value: 'seller' }]
const ADMIN_ROLE_TABS = [{ label: '买家申请', value: 'buyer' }, { label: '卖家处理', value: 'seller' }]

Page({
  data: { roleTabs: ROLE_TABS, tabs: TABS, activeRoleIndex: 0, activeTab: 0, refunds: [], role: 'buyer', orderId: '', isAdmin: false, page: 1, pageSize: 10, total: 0, loading: false, loadError: false, finished: false, pendingCount: 0 },
  onLoad(options) { const role = options.role || 'buyer'; this.setData({ role, activeRoleIndex: role === 'seller' ? 1 : 0, orderId: options.order_id || '' }) },
  onShow() { if (!requireLogin()) return; const isAdmin = hasRole('admin'); this.setData({ isAdmin, roleTabs: isAdmin ? ADMIN_ROLE_TABS : ROLE_TABS }); this.refreshList() },
  onPullDownRefresh() { this.refreshList().finally(() => wx.stopPullDownRefresh()) },
  onReachBottom() { if (!this.data.finished && !this.data.loading) this.loadRefunds(false) },
  selectTab(event) { this.setData({ activeTab: Number(event.currentTarget.dataset.index) }); this.refreshList() },
  selectRole(event) { const index = Number(event.currentTarget.dataset.index); const role = this.data.roleTabs[index] ? this.data.roleTabs[index].value : 'buyer'; this.setData({ activeRoleIndex: index, role, activeTab: 0 }); this.refreshList() },
  refreshList() { this.setData({ page: 1, refunds: [], finished: false, loadError: false }); return this.loadRefunds(true) },
  loadRefunds(reset) { const tab = this.data.tabs[this.data.activeTab]; const params = { role: this.data.role, page: this.data.page, page_size: this.data.pageSize }; if (tab.value) params.status = tab.value; if (this.data.orderId) params.order_id = this.data.orderId; const url = this.data.isAdmin ? '/admin/refunds' : '/refunds'; this.setData({ loading: true, loadError: false }); return api.get(url, params, { loading: reset, loadingText: '加载售后' }).then((data) => { const items = (data.items || []).map((item) => Object.assign({}, item, { product: Object.assign({}, item.product || {}, { title: safeText(item.product && item.product.title, '售后商品') }), status_text: refundStatus(item.status, item.status_group), amount_text: money(item.display_amount || item.request_amount || item.amount), created_text: formatDateTime(item.created_at), reason_display: safeText(item.reason_text || item.reason, '未填写'), counterparty: Object.assign({}, item.counterparty || {}, { nickname: safeText(item.counterparty && item.counterparty.nickname, '校内同学') }) })); const refunds = reset ? items : this.data.refunds.concat(items); const total = Number((data.pagination || {}).total || refunds.length); this.setData({ refunds, total, page: this.data.page + 1, finished: refunds.length >= total || items.length < this.data.pageSize, pendingCount: refunds.filter((item) => item.status_group === 'pending').length }); refreshUnreadBadge() }).catch(() => { this.setData({ loadError: true }); wx.showToast({ title: '售后列表加载失败，请下拉重试', icon: 'none' }) }).finally(() => this.setData({ loading: false })) },
  goDetail(event) { const id = event.currentTarget.dataset.id; if (id) wx.navigateTo({ url: `/pages/refund/detail/index?id=${id}` }) },
  copyNo(event) { const no = event.currentTarget.dataset.no; if (no) wx.setClipboardData({ data: no }) }
})
