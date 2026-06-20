const api = require('../../utils/request')
const { getToken, getUser } = require('../../utils/auth')

const EMPTY_TEXT = {
  recommend: { title: '暂无推荐商品', description: '先浏览几件商品，系统会逐步推荐更合适的内容' },
  latest: { title: '暂无最新商品', description: '发布新商品后会出现在这里' },
  hot: { title: '暂无热门商品', description: '有浏览和收藏后会形成热门列表' }
}

const CATEGORIES = [
  { code: 'digital', name: '数码电子', icon: '▥' },
  { code: 'book', name: '教材书籍', icon: '书' },
  { code: 'clothing', name: '服饰鞋包', icon: '衣' },
  { code: 'home', name: '生活家居', icon: '灯' },
  { code: '', name: '全部分类', icon: '••' }
]

Page({
  data: {
    loading: false,
    products: [],
    keyword: '',
    categories: CATEGORIES,
    activeCategory: '',
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
  },
  onShow() {
    const authKey = this.getAuthKey()
    if (authKey !== this.data.authKey) this.setData({ authKey, products: [] })
    this.loadProducts(this.data.activeMode)
  },
  getAuthKey() {
    const user = getUser() || {}
    return `${getToken() || ''}:${user.id || ''}`
  },
  switchMode(event) {
    const mode = event.currentTarget.dataset.mode
    if (!mode || mode === this.data.activeMode) return
    this.setData({ activeMode: mode, products: [], emptyTitle: EMPTY_TEXT[mode].title, emptyDescription: EMPTY_TEXT[mode].description })
    this.loadProducts(mode, false)
  },
  loadProducts(mode, allowFallback = true) {
    const activeMode = mode || this.data.activeMode
    this.setData({ loading: true })
    const params = { page: 1, page_size: 20, mode: activeMode }
    if (this.data.keyword) params.keyword = this.data.keyword
    if (this.data.activeCategory) params.category = this.data.activeCategory
    api.get('/products', params).then((data) => {
      const items = data.items || []
      if (activeMode === 'recommend' && !items.length && allowFallback) {
        wx.showToast({ title: '暂无推荐，已显示最新商品', icon: 'none' })
        this.setData({ activeMode: 'latest', emptyTitle: EMPTY_TEXT.latest.title, emptyDescription: EMPTY_TEXT.latest.description })
        return this.loadProducts('latest', false)
      }
      this.setData({ products: items, emptyTitle: EMPTY_TEXT[activeMode].title, emptyDescription: EMPTY_TEXT[activeMode].description })
    }).catch(() => wx.showToast({ title: '商品加载失败，请稍后重试', icon: 'none' })).finally(() => this.setData({ loading: false }))
  },
  onKeywordInput(event) { this.setData({ keyword: event.detail.value }) },
  goSearch() { this.loadProducts(this.data.activeMode, false) },
  goCategory(event) {
    const code = event.currentTarget.dataset.code || ''
    this.setData({ activeCategory: code, products: [] })
    this.loadProducts(this.data.activeMode, false)
  },
  openFilter() {
    const params = []
    if (this.data.activeCategory) params.push(`category=${encodeURIComponent(this.data.activeCategory)}`)
    if (this.data.keyword) params.push(`keyword=${encodeURIComponent(this.data.keyword)}`)
    wx.navigateTo({ url: `/pages/category/index${params.length ? `?${params.join('&')}` : ''}` })
  }
})
