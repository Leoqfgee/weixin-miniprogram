const { requireLogin, hasRole } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    products: []
  },
  onLoad() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可访问', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadProducts()
  },
  loadProducts() {
    api.get('/admin/products', { status: 'on_sale', page: 1, page_size: 50 }, { loading: true })
      .then((data) => this.setData({ products: data.items || [] }))
  },
  offShelf(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '确认下架',
      content: '商品下架后不会出现在首页、分类和猜你喜欢。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${id}/off-shelf`, { reason: '管理员下架' }, { loading: true }).then(() => {
          wx.showToast({ title: '已下架', icon: 'success' })
          this.loadProducts()
        })
      }
    })
  }
})
