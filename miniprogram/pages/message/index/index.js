const api = require('../../../utils/request')
const { requireLogin, getToken, getUser } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')
const { normalizeImageUrl } = require('../../../utils/image')
const { safeText, formatChatTime, orderStatusText } = require('../../../utils/format')

function getAuthKey() {
  const user = getUser() || {}
  return `${getToken() || ''}:${user.id || ''}`
}

function formatConversation(item) {
  const other = item.other_user || {}
  const product = item.product || {}
  const order = item.order || {}
  const last = item.last_message || {}
  const isService = item.type === 'service' || item.is_service
  const content = last.message_type === 'image' ? '\u3010\u56fe\u7247\u3011' : safeText(last.content, '\u6682\u65e0\u65b0\u6d88\u606f')
  const status = item.status_text || order.status_text || orderStatusText(item.order_status || order.status || product.status)
  return Object.assign({}, item, {
    is_service: isService,
    avatar_url: normalizeImageUrl(other.avatar || other.avatar_url || (isService ? '/assets/tabbar/message-active.png' : '/assets/tabbar/mine.png'), 'avatar'),
    display_name: safeText(other.nickname || item.title, isService ? '\u5e73\u53f0\u5ba2\u670d' : '\u6821\u56ed\u540c\u5b66'),
    display_product: safeText(product.title || order.title || item.product_title, isService ? '\u5e73\u53f0\u670d\u52a1' : '\u5173\u8054\u5546\u54c1'),
    display_message: content,
    display_time: formatChatTime(last.created_at || item.updated_at || item.created_at),
    display_status: safeText(status, isService ? '\u5ba2\u670d' : '\u4ea4\u6613\u4e2d')
  })
}

Page({
  data: {
    conversations: [],
    authKey: ''
  },
  onShow() {
    if (!requireLogin()) {
      this.setData({ conversations: [], authKey: '' })
      return
    }
    const authKey = getAuthKey()
    if (authKey !== this.data.authKey) this.setData({ conversations: [], authKey })
    this.loadConversations()
  },
  loadConversations() {
    api.get('/messages/conversations').then((data) => {
      this.setData({ conversations: (data.items || []).map(formatConversation) })
      refreshUnreadBadge()
    })
  },
  goChat(event) {
    const item = this.data.conversations[Number(event.currentTarget.dataset.index)]
    if (!item) return
    const other = item.other_user || {}
    const product = item.product || {}
    wx.navigateTo({
      url: `/pages/message/chat/index?conversation_id=${item.conversation_id || item.id}&receiver_id=${other.id || ''}&product_id=${product.id || ''}&order_id=${item.order_id || ''}&product_title=${encodeURIComponent(product.title || '')}&product_price=${product.price || ''}&product_cover=${encodeURIComponent(normalizeImageUrl(product.cover_image, 'product'))}`
    })
  }
})
