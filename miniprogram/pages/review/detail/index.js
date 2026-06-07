const api = require('../../../utils/request')

Page({
  data: { review: null },
  onLoad(options) {
    api.get(`/reviews/${options.id}`, {}, { loading: true }).then((review) => this.setData({ review }))
  }
})
