const api = require('../../utils/request')
const { getToken, getUser } = require('../../utils/auth')

Page({
  data: {
    loading: false,
    products: [],
    keyword: '',
    categories: [],
    authKey: ''
  },

  onLoad() {
    this.setData({ authKey: this.getAuthKey() })
    this.loadProducts()
    this.loadCategories()
  },
  onShow() {
    const authKey = this.getAuthKey()
    if (authKey !== this.data.authKey) {
      this.setData({ authKey, products: [] })
      this.loadCategories()
    }
    this.loadProducts()
  },
  getAuthKey() {
    const user = getUser() || {}
    return `${getToken() || ''}:${user.id || ''}`
  },

  loadProducts() {
    this.setData({ loading: true })
    api.get('/products', { page: 1, page_size: 10 })
      .then((data) => {
        this.setData({ products: data.items || [] })
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
