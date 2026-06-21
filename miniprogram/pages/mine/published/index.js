const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { productStatusText, formatDateTime, normalizeCampusText } = require('../../../utils/format')
const { DEFAULT_PRODUCT_IMAGE, normalizeImageUrl } = require('../../../utils/image')

const STATUS_NOTES = {
  sold: '交易已完成，可删除记录或重新发布',
  off_shelf: '商品已下架，可编辑、删除或重新发布',
  taken_down: '因举报成立已下架，可查看处理通知或修改后重新发布',
  removed: '因举报成立已下架，可查看处理通知或修改后重新发布'
}

Page({
  data: {
    products: [],
    statusIndex: 0,
    statusOptions: [
      { label: '在售', value: 'on_sale' },
      { label: '草稿', value: 'draft' },
      { label: '已售出', value: 'sold' },
      { label: '已下架', value: 'off_shelf' },
      { label: '举报下架', value: 'taken_down' }
    ]
  },
  onShow() {
    if (requireLogin()) this.loadProducts()
  },
  selectStatus(event) {
    this.setData({ statusIndex: Number(event.currentTarget.dataset.index) })
    this.loadProducts()
  },
  loadProducts() {
    const option = this.data.statusOptions[this.data.statusIndex]
    api.get('/products/mine', { page: 1, page_size: 50, status: option.value }, { loading: true }).then((data) => {
      const products = (data.items || []).map((item) => ({
        ...item,
        cover_image: normalizeImageUrl(item.cover_image || (Array.isArray(item.images) && item.images[0]), 'product'),
        status_text: productStatusText(item.status),
        status_note: STATUS_NOTES[item.status] || '',
        campus_text: normalizeCampusText(item.campus, ''),
        created_at_text: formatDateTime(item.created_at || item.updated_at)
      }))
      this.setData({ products })
    })
  },
  goDetail(event) {
    wx.navigateTo({ url: `/pages/product/detail/index?id=${event.currentTarget.dataset.id}` })
  },
  editProduct(event) {
    wx.navigateTo({ url: `/pages/publish/product-edit/index?id=${event.currentTarget.dataset.id}` })
  },
  onThumbError(event) {
    const index = Number(event.currentTarget.dataset.index || 0)
    this.setData({ [`products.${index}.cover_image`]: DEFAULT_PRODUCT_IMAGE })
  },
  offShelf(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '确认下架',
      content: '下架后买家将不能继续购买该商品。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${id}/off-shelf`, { reason: '从我发布的下架' }, { loading: true }).then(() => {
          wx.showToast({ title: '已下架', icon: 'success' })
          this.loadProducts()
        })
      }
    })
  },
  publishNow(event) {
    const id = event.currentTarget.dataset.id
    api.post(`/products/${id}/submit-review`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已发布', icon: 'success' })
      this.setData({ statusIndex: 0 })
      this.loadProducts()
    })
  },
  republish(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '重新发布商品',
      content: '商品将直接恢复在售。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${id}/republish`, {}, { loading: true }).then(() => {
          wx.showToast({ title: '已重新发布', icon: 'success' })
          this.setData({ statusIndex: 0 })
          this.loadProducts()
        })
      }
    })
  },
  deleteProduct(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '删除商品',
      content: '删除后不会影响历史订单，但商品将不再显示在“我发布的”。',
      confirmColor: '#C84A3A',
      success: (res) => {
        if (!res.confirm) return
        api.del(`/products/${id}`, {}, { loading: true }).then(() => {
          wx.showToast({ title: '已删除', icon: 'success' })
          this.loadProducts()
        })
      }
    })
  }
})
