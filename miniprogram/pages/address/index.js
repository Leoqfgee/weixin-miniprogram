const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')

function emptyForm() {
  return { id: '', name: '', phone: '', address: '', is_default: false }
}

function validPhone(phone) {
  return /^1[3-9]\d{9}$/.test(String(phone || '').trim())
}

Page({
  data: {
    addresses: [],
    editing: false,
    form: emptyForm()
  },
  onShow() {
    if (requireLogin()) this.loadAddresses()
  },
  loadAddresses() {
    api.get('/addresses', {}, { loading: true, loadingText: '加载地址' }).then((data) => {
      this.setData({ addresses: data.items || [] })
    }).catch(() => {
      wx.showToast({ title: '地址加载失败，请下拉重试', icon: 'none' })
    })
  },
  addAddress() {
    this.setData({ editing: true, form: emptyForm() })
  },
  editAddress(event) {
    const item = this.data.addresses[Number(event.currentTarget.dataset.index)]
    this.setData({ editing: true, form: Object.assign({}, item) })
  },
  cancelEdit() {
    this.setData({ editing: false, form: emptyForm() })
  },
  setField(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
  },
  toggleDefault(event) {
    this.setData({ 'form.is_default': event.detail.value })
  },
  validateForm() {
    const form = this.data.form
    if (!form.name.trim()) return '收货人不能为空'
    if (!form.phone.trim()) return '手机号不能为空'
    if (!validPhone(form.phone)) return '手机号格式不正确'
    if (!form.address.trim()) return '详细地址不能为空'
    return ''
  },
  saveAddress() {
    const error = this.validateForm()
    if (error) {
      wx.showToast({ title: error, icon: 'none' })
      return
    }
    const form = this.data.form
    const body = {
      name: form.name.trim(),
      phone: form.phone.trim(),
      address: form.address.trim(),
      is_default: form.is_default
    }
    const promise = form.id
      ? api.put(`/addresses/${form.id}`, body, { loading: true, loadingText: '保存中' })
      : api.post('/addresses', body, { loading: true, loadingText: '保存中' })
    promise.then(() => {
      wx.showToast({ title: '地址已保存', icon: 'success' })
      this.cancelEdit()
      this.loadAddresses()
    }).catch(() => {
      wx.showToast({ title: '地址保存失败，请稍后重试', icon: 'none' })
    })
  },
  setDefault(event) {
    api.post(`/addresses/${event.currentTarget.dataset.id}/default`, {}, { loading: true, loadingText: '设置中' }).then(() => {
      wx.showToast({ title: '已设为默认地址', icon: 'success' })
      this.loadAddresses()
    }).catch(() => {
      wx.showToast({ title: '设置默认地址失败', icon: 'none' })
    })
  },
  removeAddress(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '删除地址',
      content: '确定删除这个收货地址吗？',
      success: (res) => {
        if (!res.confirm) return
        api.del(`/addresses/${id}`, {}, { loading: true, loadingText: '删除中' }).then(() => {
          wx.showToast({ title: '地址已删除', icon: 'success' })
          this.loadAddresses()
        }).catch(() => {
          wx.showToast({ title: '删除地址失败', icon: 'none' })
        })
      }
    })
  }
})
