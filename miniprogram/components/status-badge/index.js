const { PRODUCT_STATUS_TEXT, ORDER_STATUS_TEXT } = require('../../utils/constants')

Component({
  properties: {
    status: {
      type: String,
      value: ''
    },
    type: {
      type: String,
      value: 'product'
    }
  },
  observers: {
    'status,type': function () {
      this.setData({
        text: this.getText(),
        className: this.getClassName()
      })
    }
  },
  data: {
    text: '',
    className: 'neutral'
  },
  lifetimes: {
    attached() {
      this.setData({
        text: this.getText(),
        className: this.getClassName()
      })
    }
  },
  methods: {
    getText() {
      const map = this.data.type === 'order' ? ORDER_STATUS_TEXT : PRODUCT_STATUS_TEXT
      const raw = String(this.data.status || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
      const extra = { on_sale: '在售', onsale: '在售', sale: '在售', locked: '交易中', sold: '已售出', pending: '待处理', requested: '待处理', refunding: '退款中', refunded: '已退款', rejected: '已拒绝', completed: '已完成' }
      return map[raw] || extra[raw] || '处理中'
    },
    getClassName() {
      const raw = String(this.data.status || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
      if (raw === 'on_sale' || raw === 'completed' || raw === 'sold') {
        return 'success'
      }
      if (['pending_review', 'pending_payment', 'pending_delivery', 'pending_receive', 'locked', 'refunding', 'pending', 'requested'].indexOf(raw) >= 0) {
        return 'warning'
      }
      if (raw === 'rejected' || raw === 'closed' || raw === 'refunded') {
        return 'danger'
      }
      return 'neutral'
    }
  }
})
