const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')

Page({
  data: {
    orderId: '',
    types: [
      { label: '校内面交', value: 'offline_meetup' },
      { label: '校园自提', value: 'campus_pickup' },
      { label: '校内送达', value: 'campus_delivery' },
      { label: '快递邮寄', value: 'express' }
    ],
    typeIndex: 0,
    form: {
      meet_location: '',
      meet_time: '',
      pickup_location: '',
      pickup_time_range: '',
      campus_address: '',
      delivery_note: '',
      express_company: '',
      tracking_no: '',
      proof_images: []
    }
  },
  onLoad(options) {
    requireLogin()
    this.setData({ orderId: options.order_id || '' })
  },
  onTypeChange(event) {
    this.setData({ typeIndex: Number(event.detail.value) })
  },
  onInput(event) {
    const field = event.currentTarget.dataset.field
    this.setData({ [`form.${field}`]: event.detail.value })
  },
  chooseProof() {
    const remain = 6 - this.data.form.proof_images.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传 6 张', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => this.uploadProof(res.tempFiles || [])
    })
  },
  uploadProof(files) {
    if (!files.length) return
    wx.showLoading({ title: '上传凭证' })
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'delivery' }
    }))).then((items) => {
      const urls = items.map((item) => item.url)
      this.setData({ 'form.proof_images': this.data.form.proof_images.concat(urls).slice(0, 6) })
      wx.showToast({ title: '凭证已上传', icon: 'success' })
    }).finally(() => wx.hideLoading())
  },
  removeProof(event) {
    const images = this.data.form.proof_images.slice()
    images.splice(event.currentTarget.dataset.index, 1)
    this.setData({ 'form.proof_images': images })
  },
  buildPayload() {
    const deliveryType = this.data.types[this.data.typeIndex].value
    return Object.assign({}, this.data.form, { delivery_type: deliveryType })
  },
  submit() {
    api.post(`/deliveries/${this.data.orderId}/seller-deliver`, this.buildPayload(), { loading: true }).then(() => {
      wx.showToast({ title: '已确认交付', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    })
  }
})
