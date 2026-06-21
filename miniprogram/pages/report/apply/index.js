const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { normalizeImageUrl } = require('../../../utils/image')

const reasons = [
  { label: '虚假商品/描述不符', value: 'fake_info' },
  { label: '价格异常/诱导交易', value: 'abnormal_price' },
  { label: '违禁品/违规内容', value: 'prohibited' },
  { label: '盗图/侵犯权益', value: 'infringement' },
  { label: '垃圾广告/重复发布', value: 'spam' },
  { label: '辱骂骚扰/不当言论', value: 'harassment' },
  { label: '欺诈风险', value: 'fraud' },
  { label: '其他', value: 'other' }
]

Page({
  data: {
    productId: '',
    product: null,
    reasons,
    reasonType: '',
    description: '',
    evidenceImages: []
  },
  onLoad(options) {
    requireLogin()
    this.setData({ productId: options.product_id || '' })
    this.loadProduct()
  },
  loadProduct() {
    api.get(`/products/${this.data.productId}`, {}, { loading: true }).then((product) => {
      this.setData({
        product: Object.assign({}, product, {
          cover_image: normalizeImageUrl(product.cover_image || (product.images && product.images[0]), 'product')
        })
      })
    })
  },
  chooseReason(event) {
    this.setData({ reasonType: event.currentTarget.dataset.value })
  },
  onDescription(event) {
    this.setData({ description: event.detail.value.slice(0, 200) })
  },
  chooseEvidence() {
    wx.chooseMedia({
      count: 3 - this.data.evidenceImages.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => this.uploadEvidence(res.tempFiles || [])
    })
  },
  uploadEvidence(files) {
    if (!files.length) return
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'report' },
      loading: true
    }))).then((items) => {
      this.setData({ evidenceImages: this.data.evidenceImages.concat(items.map((item) => item.url)).slice(0, 3) })
    })
  },
  removeEvidence(event) {
    const evidenceImages = this.data.evidenceImages.slice()
    evidenceImages.splice(Number(event.currentTarget.dataset.index), 1)
    this.setData({ evidenceImages })
  },
  submitReport() {
    if (!this.data.reasonType) {
      wx.showToast({ title: '请选择举报原因', icon: 'none' })
      return
    }
    api.post('/reports', {
      product_id: this.data.productId,
      reason_type: this.data.reasonType,
      description: this.data.description,
      evidence_images: this.data.evidenceImages
    }, { loading: true }).then(() => {
      wx.showToast({ title: '举报已提交，平台会尽快处理', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 800)
    })
  }
})
