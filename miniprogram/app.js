const { getToken, getUser, clearAuth } = require('./utils/auth')
const { refreshUnreadBadge } = require('./utils/unread')

App({
  globalData: {
    token: '',
    user: null
  },

  onLaunch() {
    if (wx.cloud && wx.cloud.init) {
      wx.cloud.init({
        env: 'prod-d2g73fc4ha6d2e317',
        traceUser: true
      })
    }
    this.globalData.token = getToken()
    this.globalData.user = getUser()
  },

  onShow() {
    refreshUnreadBadge()
  },

  refreshAuth(token, user) {
    this.globalData.token = token || ''
    this.globalData.user = user || null
  },

  logout() {
    clearAuth()
    this.refreshAuth('', null)
  }
})
