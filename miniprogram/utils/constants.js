const ENV_CONFIG = {
  // 开发版：只用于微信开发者工具本地调试，可按电脑当前局域网 IP 修改。
  develop: {
    API_BASE_URL: 'http://10.6.14.70:5000/api/v1'
  },
  // 体验版：真实小程序预览/体验应使用公网 HTTPS 后端域名。
  trial: {
    API_BASE_URL: 'https://api.your-domain.com/api/v1'
  },
  // 正式版：上线前必须替换为已备案、已配置到小程序后台的 HTTPS 合法域名。
  release: {
    API_BASE_URL: 'https://api.your-domain.com/api/v1'
  }
}

function getEnvVersion() {
  if (typeof wx !== 'undefined' && wx.getAccountInfoSync) {
    const accountInfo = wx.getAccountInfoSync()
    return accountInfo.miniProgram.envVersion || 'develop'
  }
  return 'develop'
}

const CURRENT_ENV = getEnvVersion()
const API_BASE_URL = (ENV_CONFIG[CURRENT_ENV] || ENV_CONFIG.develop).API_BASE_URL

const STORAGE_KEYS = {
  token: 'campus_token',
  user: 'campus_user'
}

const PRODUCT_STATUS_TEXT = {
  draft: '草稿',
  pending_review: '待审核',
  on_sale: '在售',
  rejected: '已驳回',
  off_shelf: '已下架',
  deleted: '已删除'
}

const ORDER_STATUS_TEXT = {
  pending_payment: '待支付',
  paid: '已支付',
  delivering: '交付中',
  completed: '已完成',
  closed: '已关闭'
}

const CONDITION_OPTIONS = [
  { label: '全新', value: 'new' },
  { label: '几乎全新', value: 'like_new' },
  { label: '成色良好', value: 'good' },
  { label: '有使用痕迹', value: 'fair' }
]

module.exports = {
  API_BASE_URL,
  CURRENT_ENV,
  ENV_CONFIG,
  STORAGE_KEYS,
  PRODUCT_STATUS_TEXT,
  ORDER_STATUS_TEXT,
  CONDITION_OPTIONS
}
