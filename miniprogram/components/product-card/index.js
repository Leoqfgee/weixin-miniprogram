Component({
  properties: {
    product: {
      type: Object,
      value: {},
      observer(value) {
        this.prepareProduct(value || {})
      }
    }
  },
  data: {
    conditionText: '',
    campusText: '',
    coverText: '闲置'
  },
  lifetimes: {
    attached() {
      this.prepareProduct(this.data.product || {})
    }
  },
  methods: {
    prepareProduct(product) {
      const conditionMap = {
        new: '全新',
        like_new: '几乎全新',
        good: '成色良好',
        fair: '有使用痕迹'
      }
      const title = product.title || '闲置好物'
      this.setData({
        conditionText: conditionMap[product.condition] || '校内闲置',
        campusText: product.campus || (product.seller && product.seller.campus) || '校内',
        coverText: title.slice(0, 2)
      })
    },
    onTap() {
      const id = this.data.product && this.data.product.id
      if (!id) {
        return
      }
      wx.navigateTo({ url: `/pages/product/detail/index?id=${id}` })
    }
  }
})
