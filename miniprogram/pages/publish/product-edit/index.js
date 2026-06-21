const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { validateProductForm, firstError } = require('../../../utils/validator')
const { CAMPUS_OPTIONS, CONDITION_OPTIONS, classifyProduct, getCategoryName } = require('../../../utils/constants')

const blankForm = () => ({
  title: '',
  description: '',
  price: '',
  stock: 1,
  category_id: '',
  category: '',
  category_name: '',
  category_source: '',
  condition: '',
  images: [],
  campus: CAMPUS_OPTIONS[0].value
})

Page({
  data: {
    productId: '',
    categories: [],
    categoryIndex: -1,
    autoCategoryText: '填写标题和描述后自动推荐',
    selectedCategoryText: '填写标题和描述后自动推荐',
    editingOnSale: false,
    canPublish: false,
    conditionOptions: [{ label: '成色暂不填写', value: '' }].concat(CONDITION_OPTIONS),
    conditionIndex: 0,
    selectedConditionText: '成色暂不填写',
    campusOptions: CAMPUS_OPTIONS,
    campusIndex: 0,
    selectedCampusText: CAMPUS_OPTIONS[0].label,
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
      this.setData({ categories, selectedCategoryText: this.data.categoryIndex >= 0 && categories[this.data.categoryIndex] ? categories[this.data.categoryIndex].name : this.data.autoCategoryText })
      if (this.data.productId) this.loadProduct()
    })
  },
  loadProduct() {
    api.get(`/products/${this.data.productId}`, {}, { loading: true }).then((product) => {
      const categoryIndex = this.data.categories.findIndex((item) => item.code === product.category || item.id === product.category_id)
      const conditionIndex = this.data.conditionOptions.findIndex((item) => item.value === (product.condition || ''))
      const campusIndex = campusIndexOf(product.campus)
      this.setData({
        form: Object.assign(blankForm(), product, { price: String(product.price || ''), campus: campusValue(product.campus) }),
        categoryIndex,
        autoCategoryText: product.category_name || '填写标题和描述后自动推荐',
        selectedCategoryText: categoryIndex >= 0 && this.data.categories[categoryIndex] ? this.data.categories[categoryIndex].name : (product.category_name || '填写标题和描述后自动推荐'),
        conditionIndex: conditionIndex < 0 ? 0 : conditionIndex,
        selectedConditionText: this.data.conditionOptions[conditionIndex < 0 ? 0 : conditionIndex].label,
        campusIndex,
        selectedCampusText: CAMPUS_OPTIONS[campusIndex].label,
        editingOnSale: product.status === 'on_sale' || product.status === 'active',
        canPublish: ['draft', 'rejected', 'off_shelf'].includes(product.status)
      })
    })
  },
  setField(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
    if (['title', 'description'].includes(event.currentTarget.dataset.field) && this.data.categoryIndex < 0) {
      const code = classifyProduct(this.data.form.title, this.data.form.description)
      this.setData({
        autoCategoryText: `推荐：${getCategoryName(code)}`,
        'form.category': code,
        'form.category_name': getCategoryName(code),
        'form.category_source': 'auto'
      })
    }
  },
  onCategoryChange(event) {
    const index = Number(event.detail.value)
    const category = this.data.categories[index]
    this.setData({
      categoryIndex: index,
      autoCategoryText: category.name,
      selectedCategoryText: category.name,
      'form.category_id': category.id || '',
      'form.category': category.code,
      'form.category_name': category.name,
      'form.category_source': 'manual'
    })
  },
  onConditionChange(event) {
    const index = Number(event.detail.value)
    this.setData({ conditionIndex: index, selectedConditionText: this.data.conditionOptions[index].label, 'form.condition': this.data.conditionOptions[index].value })
  },
  onCampusChange(event) {
    const index = Number(event.detail.value)
    const campus = this.data.campusOptions[index] || this.data.campusOptions[0]
    this.setData({ campusIndex: index, selectedCampusText: campus.label, 'form.campus': campus.value })
  },
  onCampusTap(event) {
    const index = Number(event.currentTarget.dataset.index)
    const campus = this.data.campusOptions[index] || this.data.campusOptions[0]
    this.setData({ campusIndex: index, selectedCampusText: campus.label, 'form.campus': campus.value })
  },
  chooseImages() {
    wx.chooseMedia({
      count: 9 - this.data.form.images.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
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
    }).catch(() => {
      wx.showToast({ title: '图片上传失败，请稍后重试', icon: 'none' })
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
    const submitAction = event.currentTarget.dataset.action
    const source = this.data.form
    const autoCode = source.category || classifyProduct(source.title, source.description)
    const selectedCategory = this.data.categoryIndex >= 0 ? this.data.categories[this.data.categoryIndex] : null
    const form = {
      title: source.title,
      description: source.description,
      price: source.price === '' ? '' : Number(source.price),
      stock: Number(source.stock || 1),
      category_id: selectedCategory ? (selectedCategory.id || '') : '',
      category: selectedCategory ? selectedCategory.code : autoCode,
      category_name: selectedCategory ? selectedCategory.name : getCategoryName(autoCode),
      category_source: selectedCategory ? 'manual' : 'auto',
      condition: source.condition,
      images: source.images || [],
      cover_image: source.cover_image || '',
      campus: campusValue(source.campus)
    }
    if (submitAction === 'publish') {
      const result = validateProductForm(form)
      this.setData({ errors: result.errors })
      if (!result.valid) {
        wx.showToast({ title: firstError(result.errors, '请检查商品信息'), icon: 'none' })
        return
      }
    }
    api.put(`/products/${this.data.productId}`, form, { loading: true }).then(() => {
      if (submitAction === 'publish') {
        return api.post(`/products/${this.data.productId}/submit-review`, {}, { loading: true })
      }
      return null
    }).then(() => {
      wx.showToast({ title: submitAction === 'publish' ? '已发布' : '修改已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    }).catch(() => {
      wx.showToast({ title: '商品保存失败，请稍后重试', icon: 'none' })
    })
  }
})

function campusIndexOf(value) {
  const index = CAMPUS_OPTIONS.findIndex((item) => item.value === value)
  return index >= 0 ? index : 0
}

function campusValue(value) {
  return CAMPUS_OPTIONS[campusIndexOf(value)].value
}
