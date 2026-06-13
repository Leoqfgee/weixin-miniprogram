const api = require('../../utils/request')
const { getToken, getUser } = require('../../utils/auth')

const EMPTY_TEXT = {
  recommend: {
    title: '暂无推荐商品',
    description: '先浏览几个商品，系统会逐步推荐更合适的内容'
  },
  latest: {
    title: '暂无最新商品',
    description: '发布新商品后会出现在这里'
  },
  hot: {
    title: '暂无热门商品',
    description: '有浏览和收藏后会形成热门列表'
  }
}

Page({
  data: {
    loading: false,
    products: [],
    keyword: '',
    categories: [],
    authKey: '',
    activeMode: 'latest',
    modeTabs: [
      { label: '推荐', value: 'recommend' },
      { label: '最新', value: 'latest' },
      { label: '热门', value: 'hot' }
    ],
    emptyTitle: EMPTY_TEXT.latest.title,
    emptyDescription: EMPTY_TEXT.latest.description
  },

  onLoad() {
    this.setData({ authKey: this.getAuthKey() })
    this.loadProducts(this.data.activeMode)
    this.loadCategories()
  },

  onShow() {
    const authKey = this.getAuthKey()
    if (authKey !== this.data.authKey) {
      this.setData({ authKey, products: [] })
      this.loadCategories()
    }
    this.loadProducts(this.data.activeMode)
  },

  getAuthKey() {
    const user = getUser() || {}
    return `${getToken() || ''}:${user.id || ''}`
  },

  switchMode(event) {
    const mode = event.currentTarget.dataset.mode
    if (!mode || mode === this.data.activeMode) return
    this.setData({
      activeMode: mode,
      products: [],
      emptyTitle: EMPTY_TEXT[mode].title,
      emptyDescription: EMPTY_TEXT[mode].description
    })
    this.loadProducts(mode)
  },

  loadProducts(mode, allowFallback = true) {
    const activeMode = mode || this.data.activeMode
    this.setData({ loading: true })
    api.get('/products', { page: 1, page_size: 10, mode: activeMode })
      .then((data) => {
        const items = data.items || []
        if (activeMode === 'recommend' && !items.length && allowFallback) {
          wx.showToast({ title: '暂无推荐，已展示最新商品', icon: 'none' })
          this.setData({
            activeMode: 'latest',
            emptyTitle: EMPTY_TEXT.latest.title,
            emptyDescription: EMPTY_TEXT.latest.description
          })
          return this.loadProducts('latest', false)
        }
        this.setData({
          products: items,
          emptyTitle: EMPTY_TEXT[activeMode].title,
          emptyDescription: EMPTY_TEXT[activeMode].description
        })
      })
      .catch(() => {
        wx.showToast({ title: '商品加载失败，请稍后重试', icon: 'none' })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  loadCategories() {
    api.get('/categories')
      .then((data) => {
        this.setData({
          categories: (data.items || []).slice(0, 8).map((item) => ({
            ...item,
            short_name: (item.name || '类').slice(0, 1)
          }))
        })
      })
  },

  onKeywordInput(event) {
    this.setData({ keyword: event.detail.value })
  },

  goSearch() {
    wx.navigateTo({ url: `/pages/category/index?keyword=${encodeURIComponent(this.data.keyword || '')}` })
  },

  goCategory(event) {
    const id = event.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/category/index?category_id=${id}` })
  }
})
