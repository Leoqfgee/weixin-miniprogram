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
    conditionOptions: CONDITION_OPTIONS,
    campus: '',
    minPrice: '',
    maxPrice: '',
    dateFrom: '',
    dateTo: '',
    sortIndex: 0,
    sortOptions: [
      { label: '最新发布', value: 'newest' },
      { label: '价格从低到高', value: 'price_asc' },
      { label: '价格从高到低', value: 'price_desc' },
      { label: '热门优先', value: 'hot' }
    ]
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
  onCampusInput(event) {
    this.setData({ campus: event.detail.value })
  },
  onMinPriceInput(event) {
    this.setData({ minPrice: event.detail.value })
  },
  onMaxPriceInput(event) {
    this.setData({ maxPrice: event.detail.value })
  },
  onDateFromChange(event) {
    this.setData({ dateFrom: event.detail.value })
    this.loadProducts()
  },
  onDateToChange(event) {
    this.setData({ dateTo: event.detail.value })
    this.loadProducts()
  },
  onSortChange(event) {
    this.setData({ sortIndex: Number(event.detail.value) })
    this.loadProducts()
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
    if (this.data.campus) params.campus = this.data.campus
    if (this.data.minPrice) params.min_price = this.data.minPrice
    if (this.data.maxPrice) params.max_price = this.data.maxPrice
    if (this.data.dateFrom) params.date_from = this.data.dateFrom
    if (this.data.dateTo) params.date_to = this.data.dateTo
    params.sort = this.data.sortOptions[this.data.sortIndex].value
    api.get('/products', params, { loading: true }).then((data) => {
      this.setData({ products: data.items || [] })
    })
  }
})
