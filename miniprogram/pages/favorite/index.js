const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')

Page({
  data: {
    products: []
  },
  onShow() {
    if (requireLogin()) this.loadFavorites()
  },
  loadFavorites() {
    api.get('/favorites', {}, { loading: true }).then((data) => {
      this.setData({ products: data.items || [] })
    })
  }
})
