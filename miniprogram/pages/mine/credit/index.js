const api = require('../../../utils/request')
const { requireLogin } = require('../../../utils/auth')
const { formatDateTime } = require('../../../utils/format')

Page({
  data: {
    credit: null,
    records: []
  },
  onShow() {
    if (!requireLogin()) return
    this.loadCredit()
  },
  loadCredit() {
    api.get('/users/me/credit', {}, { loading: true }).then((credit) => {
      this.setData({ credit })
      return api.get('/users/me/credit/records', { page: 1, page_size: 50 })
    }).then((data) => {
      const records = (data.items || []).map((item) => ({
        ...item,
        created_at_text: formatDateTime(item.created_at),
        sign: item.change_value > 0 ? '+' : ''
      }))
      this.setData({ records })
    })
  }
})
