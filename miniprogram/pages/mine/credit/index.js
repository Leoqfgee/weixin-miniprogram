const api = require('../../../utils/request')
const { requireLogin, getToken, getUser, saveAuth } = require('../../../utils/auth')
const { formatDateTime } = require('../../../utils/format')

function normalizeScore(value) {
  if (value === 0 || value === '0') return 0
  if (value === undefined || value === null || value === '') return 100
  const score = Number(value)
  if (Number.isNaN(score)) return 100
  return Math.max(0, Math.min(100, score))
}

function syncCreditToCache(credit) {
  const token = getToken()
  const user = getUser()
  if (!token || !user || !credit) return
  const score = normalizeScore(credit.credit_score)
  const level = credit.credit_level || user.credit_level || '信用优秀'
  const nextUser = Object.assign({}, user, {
    credit_score: score,
    credit_level: level,
    credit: Object.assign({}, user.credit || {}, credit, {
      credit_score: score,
      credit_level: level
    }),
    profile: Object.assign({}, user.profile || {}, {
      credit_score: score,
      credit_level: level
    })
  })
  saveAuth(token, nextUser)
}

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
      const normalizedCredit = Object.assign({}, credit, {
        credit_score: normalizeScore(credit.credit_score)
      })
      syncCreditToCache(normalizedCredit)
      this.setData({ credit: normalizedCredit })
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
