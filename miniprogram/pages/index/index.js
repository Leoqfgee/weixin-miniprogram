const api = require('../../utils/request')

Page({
  data: {
    loading: false,
    products: [],
    keyword: '',
    categories: []
  },

  onLoad() {
    this.loadProducts()
    this.loadCategories()
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
        this.setData({ categories: (data.items || []).slice(0, 5) })
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
  },
  goCart() {
    wx.navigateTo({ url: '/pages/cart/index/index' })
  }
})
