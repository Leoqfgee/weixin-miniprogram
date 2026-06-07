const api = require('../../../utils/request')

Page({
  data: {
    rangeIndex: 2,
    rangeOptions: [
      { label: '日', value: 'day' },
      { label: '周', value: 'week' },
      { label: '月', value: 'month' }
    ],
    startDate: '',
    endDate: '',
    summary: {},
    products: [],
    orders: [],
    categories: [],
    users: []
  },
  onShow() {
    this.loadReports()
  },
  onRangeChange(event) {
    this.setData({ rangeIndex: Number(event.detail.value) })
    this.loadReports()
  },
  onStartChange(event) {
    this.setData({ startDate: event.detail.value })
    this.loadReports()
  },
  onEndChange(event) {
    this.setData({ endDate: event.detail.value })
    this.loadReports()
  },
  params() {
    const params = { range: this.data.rangeOptions[this.data.rangeIndex].value }
    if (this.data.startDate) params.start_date = this.data.startDate
    if (this.data.endDate) params.end_date = this.data.endDate
    return params
  },
  loadReports() {
    const params = this.params()
    api.get('/admin/reports/summary', params).then((summary) => this.setData({ summary }))
    api.get('/admin/reports/products', params).then((data) => this.setData({ products: data.items || [] }))
    api.get('/admin/reports/orders', params).then((data) => this.setData({ orders: data.items || [] }))
    api.get('/admin/reports/categories', params).then((data) => this.setData({ categories: data.items || [] }))
    api.get('/admin/reports/users', params).then((data) => this.setData({ users: data.items || [] }))
  }
})
