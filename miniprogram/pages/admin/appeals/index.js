const api = require('../../../utils/request')
const { requireLogin, hasRole } = require('../../../utils/auth')

const DELIVERY_TYPE_TEXT = {
  offline_meetup: '校内面交',
  campus_pickup: '校园自提',
  campus_delivery: '校内送达',
  express: '快递邮寄'
}

const APPEAL_STATUS_TEXT = {
  pending: '平台介入中',
  approved: '支持买家',
  rejected: '支持卖家',
  partial_refund: '部分退款',
  closed: '已关闭'
}

Page({
  data: {
    status: 'pending',
    appeals: []
  },
  onLoad() {
    if (!requireLogin()) return
    if (!hasRole('admin')) {
      wx.showToast({ title: '仅管理员可访问', icon: 'none' })
      wx.navigateBack()
      return
    }
    this.loadAppeals()
  },
  loadAppeals() {
    api.get('/admin/appeals', { status: this.data.status, page: 1, page_size: 30 }, { loading: true }).then((data) => {
      this.setData({ appeals: (data.items || []).map((item) => this.enrichAppeal(item)) })
    })
  },
  enrichAppeal(item) {
    const delivery = item.delivery || {}
    item.status_text = APPEAL_STATUS_TEXT[item.status] || item.status
    item.delivery_text = delivery.delivery_type ? DELIVERY_TYPE_TEXT[delivery.delivery_type] || delivery.delivery_type : '暂无'
    item.delivery_location = delivery.meet_location || delivery.pickup_location || delivery.campus_address || delivery.tracking_no || delivery.delivery_note || ''
    item.product_title = (item.product_snapshot && item.product_snapshot.title) || '商品快照缺失'
    item.product_price = (item.product_snapshot && item.product_snapshot.price) || '-'
    return item
  },
  setPending() {
    this.setData({ status: 'pending' })
    this.loadAppeals()
  },
  setAll() {
    this.setData({ status: '' })
    this.loadAppeals()
  },
  arbitrate(event) {
    const id = event.currentTarget.dataset.id
    const action = event.currentTarget.dataset.action
    const reasonMap = {
      refund: '管理员支持买家退款',
      reject_refund: '管理员支持卖家，驳回退款',
      partial_refund: '管理员判定部分退款',
      close: '管理员关闭申诉'
    }
    wx.showModal({
      title: '确认仲裁',
      content: reasonMap[action],
      success: (res) => {
        if (!res.confirm) return
        api.post(`/admin/appeals/${id}/arbitrate`, {
          force_action: action,
          reason: reasonMap[action]
        }, { loading: true }).then(() => {
          wx.showToast({ title: '已处理', icon: 'success' })
          this.loadAppeals()
        })
      }
    })
  }
})
