const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { validateProductForm } = require('../../../utils/validator')
const { CONDITION_OPTIONS } = require('../../../utils/constants')

const blankForm = () => ({
  title: '',
  description: '',
  price: '',
  stock: 1,
  category_id: '',
  condition: '',
  images: [],
  campus: '主校区',
  delivery_options: ['meetup', 'express']
})

Page({
  data: {
    productId: '',
    categories: [],
    categoryIndex: -1,
    editingOnSale: false,
    conditionOptions: [{ label: '成色暂不填写', value: '' }].concat(CONDITION_OPTIONS),
    conditionIndex: 0,
    form: blankForm(),
    errors: {}
  },
  onLoad(options) {
    requireLogin()
    this.setData({ productId: options.id || '' })
    this.loadCategories()
  },
  loadCategories() {
    api.get('/categories').then((data) => {
      const categories = data.items || []
      this.setData({ categories })
      if (this.data.productId) this.loadProduct()
    })
  },
  loadProduct() {
    api.get(`/products/${this.data.productId}`, {}, { loading: true }).then((product) => {
      const categoryIndex = this.data.categories.findIndex((item) => item.id === product.category_id)
      const conditionIndex = this.data.conditionOptions.findIndex((item) => item.value === (product.condition || ''))
      this.setData({
        form: Object.assign(blankForm(), product, { price: String(product.price || '') }),
        categoryIndex,
        conditionIndex: conditionIndex < 0 ? 0 : conditionIndex,
        editingOnSale: product.status === 'on_sale'
      })
    })
  },
  setField(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
  },
  onCategoryChange(event) {
    const index = Number(event.detail.value)
    this.setData({ categoryIndex: index, 'form.category_id': this.data.categories[index].id })
  },
  onConditionChange(event) {
    const index = Number(event.detail.value)
    this.setData({ conditionIndex: index, 'form.condition': this.data.conditionOptions[index].value })
  },
  chooseImages() {
    wx.chooseMedia({
      count: 9 - this.data.form.images.length,
      mediaType: ['image'],
      success: (res) => this.uploadImages(res.tempFiles || [])
    })
  },
  uploadImages(files) {
    if (!files.length) return
    Promise.all(files.map((item) => api.uploadFile({
      url: '/files/upload',
      filePath: item.tempFilePath,
      formData: { usage: 'product' },
      loading: true
    }))).then((items) => {
      this.setData({ 'form.images': this.data.form.images.concat(items.map((item) => item.url)) })
    })
  },
  removeImage(event) {
    const images = this.data.form.images.slice()
    images.splice(Number(event.currentTarget.dataset.index), 1)
    this.setData({ 'form.images': images })
  },
  requestAi(action) {
    const endpointMap = {
      title: '/ai/title',
      description: '/ai/description',
      polish: '/ai/polish'
    }
    return api.post(endpointMap[action] || '/ai/description', {
      keywords: this.data.form.title || '校园闲置好物',
      title: this.data.form.title,
      description: this.data.form.description
    }, { loading: true, loadingText: 'AI 生成中' })
  },
  useAiTitle() {
    this.requestAi('title').then((data) => {
      const suggestions = data.title_suggestions || (data.title ? [data.title] : [])
      if (!suggestions.length) {
        wx.showToast({ title: '暂未生成标题建议', icon: 'none' })
        return
      }
      wx.showActionSheet({
        itemList: suggestions,
        success: (res) => this.setData({ 'form.title': suggestions[res.tapIndex] })
      })
    })
  },
  useAiDescription() {
    this.requestAi('description').then((data) => {
      if (data.description) this.setData({ 'form.description': data.description })
    })
  },
  submit(event) {
    const submitAction = this.data.editingOnSale ? 'draft' : event.currentTarget.dataset.action
    const source = this.data.form
    const form = {
      title: source.title,
      description: source.description,
      price: this.data.form.price === '' ? '' : Number(this.data.form.price),
      stock: Number(this.data.form.stock || 1),
      category_id: source.category_id,
      condition: source.condition,
      images: source.images || [],
      cover_image: source.cover_image || '',
      campus: source.campus || '',
      delivery_options: source.delivery_options || ['meetup']
    }
    if (submitAction === 'review') {
      const result = validateProductForm(form)
      this.setData({ errors: result.errors })
      if (!result.valid) {
        wx.showToast({ title: '请补全标题、价格和库存', icon: 'none' })
        return
      }
    }
    const save = this.data.productId
      ? api.put(`/products/${this.data.productId}`, form, { loading: true })
      : api.post('/products', Object.assign({}, form, { submit_action: submitAction }), { loading: true })
    save.then((product) => {
      const id = product.id || this.data.productId
      if (this.data.productId && submitAction === 'review') {
        return api.post(`/products/${id}/submit-review`, {}, { loading: true }).then(() => ({ id }))
      }
      return { id }
    }).then((product) => {
      wx.showToast({ title: this.data.editingOnSale ? '修改已保存' : (submitAction === 'review' ? '已提交审核' : '草稿已保存'), icon: 'success' })
      if (this.data.productId) {
        setTimeout(() => wx.navigateBack(), 400)
      } else {
        wx.redirectTo({ url: `/pages/product/detail/index?id=${product.id}` })
      }
    })
  }
})
