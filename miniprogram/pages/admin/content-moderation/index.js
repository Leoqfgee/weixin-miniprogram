const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

const categories = [
  { label: '通用', value: 'default' },
  { label: '辱骂骚扰', value: 'harassment' },
  { label: '欺诈风险', value: 'fraud' },
  { label: '违规商品', value: 'illegal_product' },
  { label: '虚假身份', value: 'fake_identity' },
  { label: '恶意交易', value: 'malicious_trade' }
]

const severities = [
  { label: '低风险', value: 'low' },
  { label: '中风险', value: 'medium' },
  { label: '高风险', value: 'high' }
]

Page({
  data: {
    words: [],
    records: [],
    categories,
    severities,
    wordText: '',
    category: 'default',
    severity: 'medium'
  },
  onShow() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可见', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadData()
  },
  loadData() {
    api.get('/admin/banned-words', {}, { loading: true }).then((data) => {
      this.setData({ words: data.items || [] })
    })
    api.get('/admin/content-block-records', { page: 1, page_size: 20 }).then((data) => {
      this.setData({ records: data.items || [] })
    })
  },
  onWordInput(event) {
    this.setData({ wordText: event.detail.value })
  },
  chooseCategory(event) {
    this.setData({ category: event.currentTarget.dataset.value })
  },
  chooseSeverity(event) {
    this.setData({ severity: event.currentTarget.dataset.value })
  },
  addWords() {
    const words = this.data.wordText
      .split(/[\n,，;；\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (!words.length) {
      wx.showToast({ title: '请填写违禁词', icon: 'none' })
      return
    }
    const uniqueWords = Array.from(new Set(words))
    Promise.all(uniqueWords.map((word) => api.post('/admin/banned-words', {
      word,
      category: this.data.category,
      severity: this.data.severity,
      enabled: true
    }))).then(() => {
      wx.showToast({ title: `已添加 ${uniqueWords.length} 个`, icon: 'success' })
      this.setData({ wordText: '' })
      this.loadData()
    }).catch((err) => {
      wx.showToast({ title: err.message || '添加失败，请检查是否重复', icon: 'none' })
      this.loadData()
    })
  },
  toggleWord(event) {
    const id = event.currentTarget.dataset.id
    const enabled = event.currentTarget.dataset.enabled === 'true' || event.currentTarget.dataset.enabled === true
    api.put(`/admin/banned-words/${id}`, { enabled: !enabled }, { loading: true }).then(() => this.loadData())
  },
  deleteWord(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '删除违禁词',
      content: '确认删除该违禁词？',
      success: (res) => {
        if (res.confirm) api.del(`/admin/banned-words/${id}`, {}, { loading: true }).then(() => this.loadData())
      }
    })
  },
  categoryLabel(value) {
    const item = categories.find((option) => option.value === value)
    return item ? item.label : value
  }
})
