const { PRODUCT_STATUS_TEXT, ORDER_STATUS_TEXT } = require('../../utils/constants')

Component({
  properties: {
    status: { type: String, value: '' },
    type: { type: String, value: 'product' }
  },
  observers: {
    'status,type': function () {
      this.refresh()
    }
  },
  data: {
    text: '',
    className: 'neutral'
  },
  lifetimes: {
    attached() {
      this.refresh()
    }
  },
  methods: {
    refresh() {
      this.setData({ text: this.getText(), className: this.getClassName() })
    },
    getText() {
      const map = this.data.type === 'order' ? ORDER_STATUS_TEXT : PRODUCT_STATUS_TEXT
      const raw = normalizeKey(this.data.status)
      const extra = {
        pending: '待处理',
        approved: '举报成立',
        rejected: this.data.type === 'report' ? '未发现违规' : (map.rejected || '未发现违规'),
        malicious: '恶意举报',
        requested: '待处理',
        refunding: '退款中',
        refunded: '已退款',
        completed: '已完成'
      }
      return map[raw] || extra[raw] || '处理中'
    },
    getClassName() {
      const raw = normalizeKey(this.data.status)
      if (['on_sale', 'active', 'completed', 'sold', 'approved'].indexOf(raw) >= 0) return 'success'
      if (['pending_review', 'pending_payment', 'pending_delivery', 'pending_receive', 'locked', 'refunding', 'pending', 'requested'].indexOf(raw) >= 0) return 'warning'
      if (['rejected', 'closed', 'refunded', 'off_shelf', 'taken_down', 'removed', 'malicious'].indexOf(raw) >= 0) return 'danger'
      return 'neutral'
    }
  }
})

function normalizeKey(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}
