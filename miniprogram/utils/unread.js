const api = require('./request')
const { getToken } = require('./auth')

function refreshUnreadBadge() {
  if (!getToken()) {
    wx.removeTabBarBadge({ index: 2, fail: () => {} })
    return Promise.resolve(0)
  }
  return api.get('/messages/conversations')
    .then((data) => {
      const total = (data.items || []).reduce((sum, item) => sum + Number(item.unread_count || 0), 0)
      if (total > 0) {
        wx.setTabBarBadge({ index: 2, text: total > 99 ? '99+' : String(total), fail: () => {} })
      } else {
        wx.removeTabBarBadge({ index: 2, fail: () => {} })
      }
      return total
    })
    .catch(() => 0)
}

module.exports = {
  refreshUnreadBadge
}
