const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')
const { normalizeImageUrl } = require('../../../utils/image')
const { safeText, formatShortDate, orderStatus } = require('../../../utils/format')

function conversationStatus(item) {
  if (item.refund && item.refund.status_text) return item.refund.status_text
  if (item.refund && item.refund.status) return item.refund.status === 'pending' ? '售后中' : safeText(item.refund.status, '售后中')
  if (item.order && item.order.status) return orderStatus(item.order.status)
  if (item.order_status) return orderStatus(item.order_status)
  return item.product ? '交易中' : '平台消息'
}

Page({
  data: { conversations: [] },
  onShow() { if (requireLogin()) this.loadConversations() },
  loadConversations() {
    api.get('/messages/conversations').then((data) => {
      const conversations = (data.items || []).map((item) => {
        const last = item.last_message || {}
        const product = item.product || {}
        return Object.assign({}, item, {
          other_user: item.other_user || {},
          product,
          display_name: safeText(item.other_user && item.other_user.nickname, '会话'),
          display_product: safeText(product.title || item.order_title, item.is_service ? '平台客服' : '关联交易'),
          display_message: last.message_type === 'image' ? '[图片]' : safeText(last.content, '暂无消息'),
          display_time: formatShortDate(last.created_at || item.updated_at || item.created_at),
          display_status: conversationStatus(item),
          service: item.is_service || !item.product
        })
      })
      this.setData({ conversations })
      refreshUnreadBadge()
    })
  },
  goChat(event) {
    const item = this.data.conversations[Number(event.currentTarget.dataset.index)]
    if (!item) return
    const other = item.other_user || {}
    const product = item.product || {}
    wx.navigateTo({ url: `/pages/message/chat/index?conversation_id=${item.conversation_id || item.id}&receiver_id=${other.id || ''}&product_id=${product.id || ''}&order_id=${item.order_id || ''}&product_title=${encodeURIComponent(product.title || '')}&product_price=${product.price || ''}&product_cover=${encodeURIComponent(normalizeImageUrl(product.cover_image, 'product'))}` })
  }
})
