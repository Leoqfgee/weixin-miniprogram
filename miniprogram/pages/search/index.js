const api = require('../../utils/request')
const { normalizeImageUrl } = require('../../utils/image')

const HISTORY_KEY = 'campus_search_history_local'

function unique(list) {
  const result = []
  ;(list || []).forEach((item) => {
    const text = String(item || '').trim()
    if (text && result.indexOf(text) < 0) result.push(text)
  })
  return result
}

function readLocalHistory() {
  return wx.getStorageSync(HISTORY_KEY) || []
}

function saveLocalHistory(keyword) {
  const text = String(keyword || '').trim()
  if (!text) return []
  const next = unique([text].concat(readLocalHistory())).slice(0, 12)
  wx.setStorageSync(HISTORY_KEY, next)
  return next
}

Page({
  data: {
    keyword: '',
    loading: false,
    searched: false,
    aiEnabled: false,
    aiMessage: '',
    resultTab: 'products',
    products: [],
    users: [],
    history: [],
    commonBought: [],
    commonViewed: [],
    tabs: [
      { label: '商品', value: 'products' },
      { label: '用户', value: 'users' }
    ]
  },

  onLoad(options) {
    const keyword = options.q ? decodeURIComponent(options.q) : ''
    this.setData({ keyword, history: readLocalHistory() })
    this.loadMeta()
    if (keyword) this.doSearch()
  },

  onShow() {
    this.loadMeta()
  },

  goBack() {
    wx.navigateBack()
  },

  onInput(event) {
    this.setData({ keyword: event.detail.value })
  },

  toggleAi(event) {
    this.setData({ aiEnabled: !!event.detail.value })
  },

  loadMeta() {
    api.get('/search/meta', {}, { silentError: true }).then((data) => {
      const local = readLocalHistory()
      this.setData({
        history: unique((data.history || []).concat(local)).slice(0, 12),
        commonBought: data.common_bought || [],
        commonViewed: data.common_viewed || []
      })
    }).catch(() => {
      this.setData({ history: readLocalHistory() })
    })
  },

  doSearch() {
    const keyword = this.data.keyword.trim()
    if (!keyword) {
      wx.showToast({ title: '请输入搜索内容', icon: 'none' })
      return
    }
    const history = saveLocalHistory(keyword)
    this.setData({ loading: true, searched: true, aiMessage: '', history })
    api.get('/search', {
      q: keyword,
      type: 'all',
      ai: this.data.aiEnabled ? '1' : '0',
      page: 1,
      page_size: 20
    }, { loading: true }).then((data) => {
      const products = (data.products && data.products.items) || []
      const users = ((data.users && data.users.items) || []).map((item) => Object.assign({}, item, {
        avatar_url: normalizeImageUrl(item.avatar_url || item.avatar || '', 'avatar')
      }))
      const aiInfo = data.ai_search || {}
      const nextTab = products.length ? 'products' : (users.length ? 'users' : this.data.resultTab)
      this.setData({
        products,
        users,
        resultTab: nextTab,
        aiMessage: this.data.aiEnabled ? (aiInfo.message || (aiInfo.used ? 'AI智搜已启用' : 'AI智搜未启用，已使用普通搜索')) : ''
      })
      this.loadMeta()
    }).catch((err) => {
      const message = err && err.message ? err.message : '搜索失败，请稍后重试'
      wx.showToast({ title: message, icon: 'none' })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  useKeyword(event) {
    const keyword = event.currentTarget.dataset.keyword || ''
    this.setData({ keyword })
    this.doSearch()
  },

  clearHistory() {
    wx.removeStorageSync(HISTORY_KEY)
    this.setData({ history: [] })
    api.del('/search/history', {}, { silentError: true }).catch(() => {})
  },

  switchTab(event) {
    this.setData({ resultTab: event.currentTarget.dataset.tab || 'products' })
  },

  openUser(event) {
    const id = event.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/profile/home/index?id=${id}` })
  }
})
