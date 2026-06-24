const api = require('../../../utils/request')
const { hasRole } = require('../../../utils/auth')

const STATUS_TABS = [
  { key: 'pending', label: '待审核', value: 'pending' },
  { key: 'approved', label: '已通过', value: 'approved' },
  { key: 'rejected', label: '已驳回', value: 'rejected' }
]

Page({
  data: {
    tabs: STATUS_TABS,
    currentTab: 'pending',
    applications: [],
    pendingCount: 0,
    selected: null,
    adminNote: '',
    loading: false
  },

  onLoad() {
    if (!hasRole('admin')) {
      wx.showToast({ title: '无权限访问', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    this.loadApplications()
  },

  onShow() {
    if (hasRole('admin')) {
      this.loadApplications()
    }
  },

  loadApplications() {
    this.setData({ loading: true })
    api.get('/admin/student-verifications', {
      status: this.data.currentTab,
      page: 1,
      page_size: 50
    }, { loading: true }).then((data) => {
      this.setData({
        applications: data.items || [],
        pendingCount: data.pending_count || 0,
        loading: false
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },

  onTabChange(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ currentTab: tab, selected: null, adminNote: '' })
    this.loadApplications()
  },

  selectApplication(e) {
    const id = e.currentTarget.dataset.id
    api.get(`/admin/student-verifications/${id}`, {}, { loading: true }).then((application) => {
      this.setData({
        selected: application,
        adminNote: application.admin_note || ''
      })
    })
  },

  closeDetail() {
    this.setData({ selected: null, adminNote: '' })
  },

  onNoteChange(e) {
    this.setData({ adminNote: e.detail.value })
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url
    const urls = e.currentTarget.dataset.urls || [url]
    wx.previewImage({ current: url, urls: urls })
  },

  approveApplication() {
    if (!this.data.selected) return
    this.reviewApplication('approved')
  },

  rejectApplication() {
    if (!this.data.selected) return
    this.reviewApplication('rejected')
  },

  reviewApplication(result) {
    const selected = this.data.selected
    wx.showModal({
      title: result === 'approved' ? '确认通过' : '确认驳回',
      content: result === 'approved'
        ? '确认通过该学生的认证申请？'
        : '确认驳回该学生的认证申请？驳回后用户可重新申请。',
      success: (res) => {
        if (res.confirm) {
          api.post(`/admin/student-verifications/${selected.id}/review`, {
            result: result,
            admin_note: this.data.adminNote
          }, { loading: true }).then(() => {
            wx.showToast({
              title: result === 'approved' ? '已通过' : '已驳回',
              icon: 'success'
            })
            this.setData({ selected: null, adminNote: '' })
            this.loadApplications()
          }).catch((err) => {
            wx.showToast({ title: err.message || '操作失败', icon: 'none' })
          })
        }
      }
    })
  },

  goUserProfile() {
    if (!this.data.selected) return
    wx.navigateTo({
      url: `/pages/profile/home/index?id=${this.data.selected.user.id}`
    })
  }
})