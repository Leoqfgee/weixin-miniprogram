const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')
const { normalizeImageUrl } = require('../../../utils/image')

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
      refreshUnreadBadge()
    })
  },
  goChat(event) {
    const item = this.data.conversations[Number(event.currentTarget.dataset.index)]
    if (!item) return
    const other = item.other_user || {}
    const product = item.product || {}
    wx.navigateTo({
      url: `/pages/message/chat/index?conversation_id=${item.conversation_id || item.id}&receiver_id=${other.id || ''}&product_id=${product.id || ''}&product_title=${encodeURIComponent(product.title || '')}&product_price=${product.price || ''}&product_cover=${encodeURIComponent(normalizeImageUrl(product.cover_image, 'product'))}`
    })
  }
})
