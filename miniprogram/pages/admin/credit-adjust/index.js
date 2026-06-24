const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

Page({
  data: {
    keyword: '',
    users: [],
    selected: null,
    records: [],
    targetScore: '',
    reasonText: ''
  },
  onShow() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可见', icon: 'none' })
      wx.navigateBack()
    }
  },
  onKeyword(event) {
    this.setData({ keyword: event.detail.value })
  },
  searchUsers() {
    if (!this.data.keyword.trim()) {
      wx.showToast({ title: '请输入用户关键词', icon: 'none' })
      return
    }
    api.get('/admin/users/search', { q: this.data.keyword, page_size: 20 }, { loading: true }).then((data) => {
      this.setData({ users: data.items || [] })
    })
  },
  selectUser(event) {
    const id = event.currentTarget.dataset.id
    const user = (this.data.users || []).find((item) => item.id === id)
    if (!user) return
    api.get('/admin/users/search', { q: user.nickname, user_id: user.id }, { loading: true }).then((data) => {
      this.setData({ selected: user, records: data.credit_records || [], targetScore: '', reasonText: '' })
    })
  },
  onInput(event) {
    const field = event.currentTarget.dataset.field
    let value = event.detail.value
    if (field === 'targetScore') {
      value = String(value || '').replace(/[^0-9]/g, '')
      if (value.length > 3) value = value.slice(0, 3)
    }
    this.setData({ [field]: value })
  },
  adjustCredit() {
    const selected = this.data.selected
    const rawTargetScore = String(this.data.targetScore || '').trim()
    const targetScore = Number(rawTargetScore)
    if (!selected) return
    if (!rawTargetScore || !Number.isInteger(targetScore)) {
      wx.showToast({ title: '请填写 0-100 的信用分', icon: 'none' })
      return
    }
    if (targetScore < 0 || targetScore > 100) {
      wx.showToast({ title: '信用分只能是 0-100', icon: 'none' })
      return
    }
    if (targetScore === Number(selected.credit_score)) {
      wx.showToast({ title: '信用分未变化', icon: 'none' })
      return
    }
    if (!this.data.reasonText.trim()) {
      wx.showToast({ title: '请填写调整原因', icon: 'none' })
      return
    }
    wx.showModal({
      title: '确认修改信用分',
      content: `将 ${selected.nickname} 的信用分改为 ${targetScore} 分`,
      success: (res) => {
        if (!res.confirm) return
        api.post(`/admin/users/${selected.id}/credit/adjust`, {
          target_score: targetScore,
          reason_text: this.data.reasonText
        }, { loading: true }).then((data) => {
          wx.showToast({ title: '修改成功', icon: 'success' })
          const credit = data.credit || {}
          this.setData({
            selected: Object.assign({}, selected, { credit_score: credit.credit_score }),
            targetScore: '',
            reasonText: ''
          })
          this.selectUser({ currentTarget: { dataset: { id: this.data.selected.id } } })
        })
      }
    })
  }
})
