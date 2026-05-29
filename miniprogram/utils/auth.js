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

function setUser(user) {
  wx.setStorageSync(STORAGE_KEYS.user, user || null)
}

function saveAuth(token, user) {
  setToken(token)
  setUser(user)
  const app = getApp()
  if (app && app.refreshAuth) {
    app.refreshAuth(token, user)
  }
}

function clearAuth() {
  wx.removeStorageSync(STORAGE_KEYS.token)
  wx.removeStorageSync(STORAGE_KEYS.user)
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
  setUser,
  saveAuth,
  clearAuth,
  requireLogin,
  hasRole
}
