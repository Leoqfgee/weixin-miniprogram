const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')

Page({
  data: {
    activeType: 'all',
    tabs: [
      { label: '全部', value: 'all' },
      { label: '降价宝贝', value: 'price_drop' },
      { label: '有效宝贝', value: 'valid' },
      { label: '失效宝贝', value: 'invalid' }
    ],
    stats: {},
    products: []
  },
  onShow() {
    if (requireLogin()) this.loadFavorites()
  },
  switchType(event) {
    this.setData({ activeType: event.currentTarget.dataset.type }, () => this.loadFavorites())
  },
  loadFavorites() {
    api.get('/favorites', { type: this.data.activeType }, { loading: true }).then((data) => {
      this.setData({ products: data.items || [], stats: data.stats || {} })
    })
  },
  removeFavorite(event) {
    const id = event.currentTarget.dataset.id
    api.del(`/favorites/${id}`, {}, { loading: true }).then(() => {
      wx.showToast({ title: '已取消收藏', icon: 'success' })
      this.loadFavorites()
    })
  },
  cleanupInvalid() {
    api.post('/favorites/cleanup-invalid', {}, { loading: true }).then((data) => {
      wx.showToast({ title: `已清理 ${data.removed || 0} 个`, icon: 'none' })
      this.loadFavorites()
    })
  }
})
