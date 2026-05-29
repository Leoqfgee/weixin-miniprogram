const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { validateProductForm } = require('../../../utils/validator')
const { CONDITION_OPTIONS } = require('../../../utils/constants')

Page({
  data: {
    categories: [],
    categoryIndex: -1,
    conditionOptions: CONDITION_OPTIONS,
    conditionIndex: 2,
    form: {
      title: '',
      description: '',
      price: '',
      stock: 1,
      category_id: '',
      condition: 'good',
      images: [],
      campus: '主校区',
      delivery_options: ['meetup']
    },
    errors: {}
  },
  onLoad() {
    requireLogin()
    this.loadCategories()
  },
  loadCategories() {
    api.get('/categories').then((data) => {
      this.setData({ categories: data.items || [] })
    })
  },
  setField(event) {
    const field = event.currentTarget.dataset.field
    this.setData({ [`form.${field}`]: event.detail.value })
  },
  onCategoryChange(event) {
    const index = Number(event.detail.value)
    const category = this.data.categories[index]
    this.setData({ categoryIndex: index, 'form.category_id': category.id })
  },
  onConditionChange(event) {
    const index = Number(event.detail.value)
    const item = this.data.conditionOptions[index]
    this.setData({ conditionIndex: index, 'form.condition': item.value })
  },
  chooseImages() {
    wx.chooseMedia({
      count: 9,
      mediaType: ['image'],
      success: (res) => {
        this.uploadImages(res.tempFiles || [])
      }
    })
  },
  uploadImages(files) {
    if (!files.length) return
    wx.showLoading({ title: '上传图片' })
    const uploads = files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'product' }
    }))
    Promise.all(uploads)
      .then((items) => {
        const urls = items.map((item) => item.url)
        this.setData({ 'form.images': urls })
        wx.showToast({ title: '图片已上传', icon: 'success' })
      })
      .finally(() => wx.hideLoading())
  },
  useAiMock() {
    api.post('/ai/product-copy', {
      keywords: this.data.form.title || '校园闲置好物',
      title: this.data.form.title,
      description: this.data.form.description
    }, { loading: true, loadingText: '生成中' }).then((data) => {
      this.setData({
        'form.title': data.title,
        'form.description': data.description
      })
      wx.showToast({ title: '已生成建议', icon: 'success' })
    }).catch(() => {
      wx.showToast({ title: 'AI 暂不可用，可手动填写', icon: 'none' })
    })
  },
  submit(event) {
    const submitAction = event.currentTarget.dataset.action
    const form = Object.assign({}, this.data.form, {
      price: Number(this.data.form.price),
      stock: Number(this.data.form.stock)
    })
    const result = validateProductForm(form)
    this.setData({ errors: result.errors })
    if (!result.valid) {
      wx.showToast({ title: '请检查表单', icon: 'none' })
      return
    }
    api.post('/products', Object.assign({}, form, { submit_action: submitAction }), { loading: true })
      .then((product) => {
        wx.showToast({ title: submitAction === 'review' ? '已提交审核' : '已保存草稿', icon: 'success' })
        wx.navigateTo({ url: `/pages/product/detail/index?id=${product.id}` })
      })
  }
})
