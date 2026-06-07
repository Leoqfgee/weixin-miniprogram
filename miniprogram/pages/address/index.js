const api = require('../../utils/request')
const { requireLogin } = require('../../utils/auth')

function emptyForm() {
  return { id: '', name: '', phone: '', address: '', is_default: false }
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
    api.get('/addresses', {}, { loading: true }).then((data) => {
      this.setData({ addresses: data.items || [] })
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
  saveAddress() {
    const form = this.data.form
    if (!form.name.trim() || !form.phone.trim() || !form.address.trim()) {
      wx.showToast({ title: '请填写完整地址信息', icon: 'none' })
      return
    }
    const body = {
      name: form.name.trim(),
      phone: form.phone.trim(),
      address: form.address.trim(),
      is_default: form.is_default
    }
    const promise = form.id
      ? api.put(`/addresses/${form.id}`, body, { loading: true })
      : api.post('/addresses', body, { loading: true })
    promise.then(() => {
      wx.showToast({ title: '地址已保存', icon: 'success' })
      this.cancelEdit()
      this.loadAddresses()
    })
  },
  setDefault(event) {
    api.post(`/addresses/${event.currentTarget.dataset.id}/default`, {}, { loading: true }).then(() => {
      this.loadAddresses()
    })
  },
  removeAddress(event) {
    const id = event.currentTarget.dataset.id
    wx.showModal({
      title: '删除地址',
      content: '确定删除这个收货地址吗？',
      success: (res) => {
        if (!res.confirm) return
        api.del(`/addresses/${id}`, {}, { loading: true }).then(() => this.loadAddresses())
      }
    })
  }
})
