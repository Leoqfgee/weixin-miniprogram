const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')
const { formatDateTime, reportStatusText } = require('../../../utils/format')
const { normalizeImageUrl } = require('../../../utils/image')

const tabs = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '举报成立', value: 'approved' },
  { label: '未发现违规', value: 'rejected' },
  { label: '恶意举报', value: 'malicious' }
]

const typeTabs = [
  { label: '全部', value: '' },
  { label: '商品举报', value: 'product' },
  { label: '用户举报', value: 'user' }
]

Page({
  data: {
    tabs,
    typeTabs,
    activeIndex: 1,
    activeTypeIndex: 0,
    reports: [],
    pendingCount: 0,
    selected: null,
    adminNote: '',
    creditDeduct: 0
  },
  onShow() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可见', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadReports()
  },
  switchTab(event) {
    this.setData({ activeIndex: Number(event.currentTarget.dataset.index), selected: null })
    this.loadReports()
  },
  switchType(event) {
    this.setData({ activeTypeIndex: Number(event.currentTarget.dataset.index), selected: null })
    this.loadReports()
  },
  loadReports() {
    const tab = this.data.tabs[this.data.activeIndex]
    const type = this.data.typeTabs[this.data.activeTypeIndex]
    api.get('/admin/reports', { status: tab.value, target_type: type.value, page: 1, page_size: 50 }, { loading: true }).then((data) => {
      this.setData({
        pendingCount: data.pending_count || 0,
        reports: (data.items || []).map((item) => this.prepareReport(item))
      })
    })
  },
  prepareReport(item) {
    const isUser = item.target_type === 'user'
    return Object.assign({}, item, {
      status_text: item.status_text || reportStatusText(item.status),
      target_title: isUser ? ((item.target_user && item.target_user.nickname) || item.target_user_nickname_snapshot || '被举报用户') : (item.product_title_snapshot || (item.product && item.product.title) || '被举报商品'),
      target_subtitle: isUser ? '用户举报' : '商品举报',
      product_image: normalizeImageUrl(item.product_image_snapshot || (item.product && item.product.cover_image), 'product'),
      created_at_text: formatDateTime(item.created_at),
      handled_at_text: formatDateTime(item.handled_at)
    })
  },
  viewDetail(event) {
    const id = event.currentTarget.dataset.id
    api.get(`/admin/reports/${id}`, {}, { loading: true }).then((report) => {
      this.setData({
        selected: this.prepareReport(report),
        adminNote: report.admin_note || '',
        creditDeduct: report.credit_deduct || defaultDeduct(report.reason_type)
      })
    })
  },
  onNote(event) {
    this.setData({ adminNote: event.detail.value })
  },
  onDeduct(event) {
    this.setData({ creditDeduct: Number(event.detail.value || 0) })
  },
  handle(event) {
    const result = event.currentTarget.dataset.result
    const typeText = this.data.selected && this.data.selected.target_type === 'user' ? '用户举报' : '商品举报'
    const titleMap = { approved: '确认举报成立', rejected: '确认举报不成立', malicious: '确认恶意举报' }
    wx.showModal({
      title: titleMap[result],
      content: `即将处理该${typeText}，处理结果会通知相关用户。`,
      success: (res) => {
        if (!res.confirm) return
        api.post(`/admin/reports/${this.data.selected.id}/handle`, {
          result,
          admin_note: this.data.adminNote,
          credit_deduct: Number(this.data.creditDeduct || 0)
        }, { loading: true }).then(() => {
          wx.showToast({ title: '处理完成', icon: 'success' })
          this.setData({ selected: null })
          this.loadReports()
        })
      }
    })
  },
  closeDetail() {
    this.setData({ selected: null })
  },
  previewEvidence(event) {
    const urls = this.data.selected.evidence_images || []
    wx.previewImage({ current: event.currentTarget.dataset.url, urls })
  }
})

function defaultDeduct(reasonType) {
  return {
    fake_info: 10,
    abnormal_price: 10,
    prohibited: 20,
    infringement: 10,
    spam: 5,
    harassment: 10,
    fraud: 20,
    illegal_product: 20,
    malicious_trade: 10,
    fake_identity: 10,
    other: 5
  }[reasonType] || 5
}
