const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    conversations: []
  },
  onShow() {
    if (requireLogin()) {
      this.loadConversations()
    }
  },
  loadConversations() {
    api.get('/messages/conversations').then((data) => {
      this.setData({ conversations: data.items || [] })
    })
  }
})
