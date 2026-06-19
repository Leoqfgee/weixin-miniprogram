const { STORAGE_KEYS } = require('./constants')

function getToken() {
  return wx.getStorageSync(STORAGE_KEYS.token) || ''
}

function setToken(token) {
  wx.setStorageSync(STORAGE_KEYS.token, token || '')
}

function getUser() {
  return wx.getStorageSync(STORAGE_KEYS.user) || null
}

function inferLoginType(user) {
  if (!user) return ''
  if (user.phone) return 'phone'
  if (user.openid_mask) return 'wechat'
  return ''
}

function getLoginType() {
  return wx.getStorageSync(STORAGE_KEYS.loginType) || inferLoginType(getUser())
}

function setLoginType(loginType) {
  wx.setStorageSync(STORAGE_KEYS.loginType, loginType || '')
}

function setUser(user) {
  wx.setStorageSync(STORAGE_KEYS.user, user || null)
  if (user && user.id) {
    wx.setStorageSync(`${STORAGE_KEYS.userScopedPrefix}${user.id}`, user)
    wx.setStorageSync(STORAGE_KEYS.activeUserId, user.id)
  }
}

function clearAccountRuntimeState() {
  wx.removeStorageSync(STORAGE_KEYS.user)
  wx.removeStorageSync(STORAGE_KEYS.loginType)
  wx.removeStorageSync(STORAGE_KEYS.activeUserId)
}

function saveAuth(token, user, loginType) {
  const current = getUser()
  const currentLoginType = getLoginType()
  if (current && user && current.id && user.id && current.id !== user.id) {
    clearAccountRuntimeState()
  }
  setToken(token)
  setLoginType(loginType || currentLoginType || inferLoginType(user))
  setUser(user)
  const app = getApp()
  if (app && app.refreshAuth) {
    app.refreshAuth(token, user)
  }
}

function clearAuth() {
  wx.removeStorageSync(STORAGE_KEYS.token)
  clearAccountRuntimeState()
  const app = getApp()
  if (app && app.refreshAuth) {
    app.refreshAuth('', null)
  }
}

function requireLogin() {
  if (getToken()) {
    return true
  }
  wx.showToast({ title: '请先登录', icon: 'none' })
  wx.navigateTo({ url: '/pages/login/index' })
  return false
}

function hasRole(role) {
  const user = getUser()
  const roles = user && user.roles ? user.roles : []
  return roles.indexOf(role) >= 0
}

module.exports = {
  getToken,
  setToken,
  getUser,
  getLoginType,
  setUser,
  saveAuth,
  clearAuth,
  requireLogin,
  hasRole
}
