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

Page({
  data: {
    tabs,
    activeIndex: 1,
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
  loadReports() {
    const tab = this.data.tabs[this.data.activeIndex]
    api.get('/admin/reports', { status: tab.value, page: 1, page_size: 50 }, { loading: true }).then((data) => {
      this.setData({
        pendingCount: data.pending_count || 0,
        reports: (data.items || []).map((item) => ({
          ...item,
          status_text: item.status_text || reportStatusText(item.status),
          product_image: normalizeImageUrl(item.product_image_snapshot || (item.product && item.product.cover_image), 'product'),
          created_at_text: formatDateTime(item.created_at)
        }))
      })
    })
  },
  viewDetail(event) {
    const id = event.currentTarget.dataset.id
    api.get(`/admin/reports/${id}`, {}, { loading: true }).then((report) => {
      this.setData({
        selected: Object.assign({}, report, {
          status_text: report.status_text || reportStatusText(report.status),
          product_image: normalizeImageUrl(report.product_image_snapshot || (report.product && report.product.cover_image), 'product'),
          created_at_text: formatDateTime(report.created_at),
          handled_at_text: formatDateTime(report.handled_at)
        }),
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
    const titleMap = { approved: '确认举报成立', rejected: '确认举报不成立', malicious: '确认恶意举报' }
    const contentMap = {
      approved: '举报成立后商品将下架，并按扣分值扣除卖家信用分。',
      rejected: '举报不成立后商品状态不变，不扣卖家信用分。',
      malicious: '恶意举报会扣除举报人信用分，商品状态不变。'
    }
    wx.showModal({
      title: titleMap[result],
      content: contentMap[result],
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
    other: 5
  }[reasonType] || 5
}
