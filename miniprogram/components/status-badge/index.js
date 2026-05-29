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
      if (this.data.status === 'on_sale' || this.data.status === 'paid' || this.data.status === 'completed') {
        return 'success'
      }
      if (this.data.status === 'pending_review' || this.data.status === 'pending_payment') {
        return 'warning'
      }
      if (this.data.status === 'rejected' || this.data.status === 'closed') {
        return 'danger'
      }
      return 'neutral'
    }
  }
})
