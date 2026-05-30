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
      return map[this.data.status] || this.data.status || '未知'
    },
    getClassName() {
      if (this.data.status === 'on_sale' || this.data.status === 'completed' || this.data.status === 'sold') {
        return 'success'
      }
      if (['pending_review', 'pending_payment', 'pending_delivery', 'pending_receive', 'locked', 'refunding'].indexOf(this.data.status) >= 0) {
        return 'warning'
      }
      if (this.data.status === 'rejected' || this.data.status === 'closed' || this.data.status === 'refunded') {
        return 'danger'
      }
      return 'neutral'
    }
  }
})
