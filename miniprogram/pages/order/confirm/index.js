const { requireLogin } = require('../../../utils/auth')
const api = require('../../../utils/request')

Page({
  data: {
    productId: '',
    quantity: 1,
    product: null,
    deliveryType: 'offline_meetup',
    meetLocation: '图书馆门口',
    addresses: [],
    addressIndex: -1
  },
  onLoad(options) {
    requireLogin()
    this.setData({ productId: options.product_id || '', quantity: Number(options.quantity || 1) })
    this.loadProduct()
    this.loadAddresses()
  },
  loadProduct() {
    api.get(`/products/${this.data.productId}`, {}, { loading: true }).then((product) => this.setData({ product }))
  },
  loadAddresses() {
    api.get('/addresses').then((data) => {
      const addresses = data.items || []
      const defaultIndex = addresses.findIndex((item) => item.is_default)
      this.setData({ addresses, addressIndex: defaultIndex >= 0 ? defaultIndex : (addresses.length ? 0 : -1) })
    })
  },
  chooseDelivery(event) {
    this.setData({ deliveryType: event.currentTarget.dataset.value })
  },
  onLocationInput(event) {
    this.setData({ meetLocation: event.detail.value })
  },
  onAddressChange(event) {
    this.setData({ addressIndex: Number(event.detail.value) })
  },
  goAddress() {
    wx.navigateTo({ url: '/pages/address/index' })
  },
  onCreateOrder() {
    const body = {
      product_id: this.data.productId,
      quantity: this.data.quantity,
      delivery_type: this.data.deliveryType
    }
    if (this.data.deliveryType === 'express') {
      if (this.data.addressIndex < 0) {
        wx.showToast({ title: '请先添加收货地址', icon: 'none' })
        return
      }
      body.shipping_address = this.data.addresses[this.data.addressIndex]
    } else {
      body.meet_location = this.data.meetLocation
    }
    api.post('/orders', body, {
      loading: true,
      header: { 'X-Idempotency-Key': Date.now().toString(36) + Math.random().toString(36).slice(2) }
    }).then((order) => wx.redirectTo({ url: `/pages/order/detail/index?id=${order.id}` }))
  }
})
