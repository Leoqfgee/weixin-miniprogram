const api = require('../../utils/request')
const { getUser, requireLogin } = require('../../utils/auth')

Page({
  onLoad() {
    if (!requireLogin()) return
    const user = getUser() || {}
    if ((user.roles || []).indexOf('admin') >= 0) {
      wx.showToast({ title: '请在消息页处理客服会话', icon: 'none' })
      setTimeout(() => wx.switchTab({ url: '/pages/message/index/index' }), 500)
      return
    }
    api.get('/messages/support', {}, { loading: true }).then((support) => {
      wx.redirectTo({
        url: `/pages/message/chat/index?receiver_id=${support.id}&support=1`
      })
    })
  }
})
