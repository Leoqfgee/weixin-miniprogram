const { getToken, getUser, clearAuth } = require('./utils/auth')

App({
  globalData: {
    token: '',
    user: null
  },

  onLaunch() {
    this.globalData.token = getToken()
    this.globalData.user = getUser()
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
