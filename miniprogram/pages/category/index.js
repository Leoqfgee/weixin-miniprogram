const api = require('../../utils/request')
const { CONDITION_OPTIONS } = require('../../utils/constants')

Page({
  data: {
    keyword: '',
    products: [],
    categories: [],
    selectedCategoryId: '',
    categoryIndex: -1,
    conditionIndex: -1,
    conditionOptions: CONDITION_OPTIONS
  },
  onLoad(options) {
    this.setData({
      keyword: options.keyword ? decodeURIComponent(options.keyword) : '',
      selectedCategoryId: options.category_id || ''
    })
    this.loadCategories()
    this.loadProducts()
  },
  onKeywordInput(event) {
    this.setData({ keyword: event.detail.value })
  },
  loadCategories() {
    api.get('/categories').then((data) => {
      const categories = data.items || []
      const categoryIndex = categories.findIndex((item) => item.id === this.data.selectedCategoryId)
      this.setData({ categories, categoryIndex })
    })
  },
  onCategoryChange(event) {
    const categoryIndex = Number(event.detail.value)
    this.setData({
      categoryIndex,
      selectedCategoryId: this.data.categories[categoryIndex] ? this.data.categories[categoryIndex].id : ''
    })
    this.loadProducts()
  },
  onConditionChange(event) {
    this.setData({ conditionIndex: Number(event.detail.value) })
    this.loadProducts()
  },
  onSearch() {
    this.loadProducts()
  },
  loadProducts() {
    const params = { page: 1, page_size: 20 }
    if (this.data.keyword) params.keyword = this.data.keyword
    if (this.data.selectedCategoryId) params.category_id = this.data.selectedCategoryId
    if (this.data.conditionIndex >= 0) params.condition = this.data.conditionOptions[this.data.conditionIndex].value
    api.get('/products', params, { loading: true }).then((data) => {
      this.setData({ products: data.items || [] })
    })
  }
})
