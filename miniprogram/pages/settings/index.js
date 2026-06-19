const api = require('../../utils/request')
const { getToken, getUser, clearAuth, saveAuth } = require('../../utils/auth')

Page({
  data: {
    user: null,
    avatarText: '?'
  },
  onShow() {
    const cached = getUser()
    this.applyUser(cached)
    if (!getToken()) return
    api.get('/users/me').then((freshUser) => {
      saveAuth(getToken(), freshUser)
      this.applyUser(freshUser)
    })
  },
  applyUser(user) {
    const nickname = user && user.profile ? (user.profile.nickname || user.nickname || '我') : '?'
    this.setData({ user, avatarText: nickname.slice(0, 1) })
  },
  goProfileEdit() {
    wx.navigateTo({ url: '/pages/profile/edit/index' })
  },
  goAddresses() {
    wx.navigateTo({ url: '/pages/address/index' })
  },
  logout() {
    clearAuth()
    wx.showToast({ title: '已退出登录', icon: 'success' })
    setTimeout(() => wx.switchTab({ url: '/pages/mine/index/index' }), 400)
  },
  cancelAccount() {
    wx.showModal({
      title: '确认注销账号',
      content: '注销后账号将被停用并退出登录。若存在未完成订单或售后，系统会阻止注销。',
      confirmText: '确认注销',
      confirmColor: '#f04438',
      success: (res) => {
        if (!res.confirm) return
        api.del('/users/me', {}, { loading: true, loadingText: '注销中' }).then(() => {
          clearAuth()
          wx.showToast({ title: '账号已注销', icon: 'success' })
          setTimeout(() => wx.switchTab({ url: '/pages/mine/index/index' }), 500)
        })
      }
    })
  }
})
