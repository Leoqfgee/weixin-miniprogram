const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { PRODUCT_STATUS_TEXT } = require('../../../utils/constants')
const { DEFAULT_PRODUCT_IMAGE, normalizeImageUrl } = require('../../../utils/image')

const STATUS_NOTES = {
  sold: '交易已完成，可删除记录或重新发布',
  off_shelf: '商品已停止展示，可编辑、删除或重新发布'
}

Page({
  data: {
    products: [],
    statusIndex: 0,
    statusOptions: [
      { label: '在售', value: 'on_sale' },
      { label: '待审核', value: 'pending_review' },
      { label: '草稿', value: 'draft' },
      { label: '审核驳回', value: 'rejected' },
      { label: '已售出', value: 'sold' },
      { label: '已下架', value: 'off_shelf' }
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
        status_text: PRODUCT_STATUS_TEXT[item.status] || item.status,
        status_note: STATUS_NOTES[item.status] || ''
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
  submitReview(event) {
    const id = event.currentTarget.dataset.id
    api.post(`/products/${id}/submit-review`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已提交审核', icon: 'success' })
      this.loadProducts()
    })
  },
  republish(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '重新发布商品',
      content: '商品将重新提交管理员审核，审核通过后恢复在售。',
      success: (res) => {
        if (!res.confirm) return
        api.post(`/products/${id}/republish`, {}, { loading: true }).then(() => {
          wx.showToast({ title: '已重新提交审核', icon: 'success' })
          this.setData({ statusIndex: 1 })
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
