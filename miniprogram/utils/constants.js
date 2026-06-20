const CLOUD_RUN_ENV = 'prod-d2g73fc4ha6d2e317'
const CLOUD_RUN_SERVICE = 'flask-fnnj'
const API_PREFIX = '/api/v1'
const CLOUD_RUN_PUBLIC_BASE_URL = 'https://flask-fnnj-267255-4-1440900946.sh.run.tcloudbase.com/api/v1'

const ENV_CONFIG = {
  develop: {
    API_BASE_URL: CLOUD_RUN_PUBLIC_BASE_URL
  },
  trial: {
    API_BASE_URL: CLOUD_RUN_PUBLIC_BASE_URL
  },
  release: {
    API_BASE_URL: CLOUD_RUN_PUBLIC_BASE_URL
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
const DEV_TEST_LOGIN_ENABLED = CURRENT_ENV === 'develop'

const STORAGE_KEYS = {
  token: 'campus_token',
  user: 'campus_user',
  loginType: 'campus_login_type',
  activeUserId: 'campus_active_user_id',
  userScopedPrefix: 'campus_user_profile_'
}

const PRODUCT_STATUS_TEXT = {
  draft: '草稿',
  pending_review: '待审核',
  on_sale: '在售',
  locked: '交易中',
  sold: '已售出',
  rejected: '已驳回',
  off_shelf: '已下架'
}

const ORDER_STATUS_TEXT = {
  pending_payment: '待付款',
  pending_delivery: '待交付',
  pending_receive: '待收货',
  pending_review: '待评价',
  completed: '交易完成',
  closed: '已取消',
  refunding: '退款/售后中',
  refunded: '已退款'
}

const CONDITION_OPTIONS = [
  { label: '全新', value: 'new' },
  { label: '几乎全新', value: 'like_new' },
  { label: '成色良好', value: 'good' },
  { label: '有使用痕迹', value: 'fair' }
]

const CAMPUS_OPTIONS = [
  { label: '东校区', value: '东校区' },
  { label: '西校区', value: '西校区' }
]

const PRODUCT_CATEGORIES = [
  { code: 'digital', name: '数码电子' },
  { code: 'book', name: '教材书籍' },
  { code: 'clothing', name: '服饰鞋包' },
  { code: 'home', name: '生活家居' },
  { code: 'other', name: '其他' }
]

function getCategoryName(code) {
  const item = PRODUCT_CATEGORIES.find((category) => category.code === code)
  return item ? item.name : '其他'
}

function classifyProduct(title, description) {
  const text = `${title || ''} ${description || ''}`.toLowerCase()
  const rules = [
    ['digital', ['手机', '电脑', '耳机', '键盘', '鼠标', '充电宝', '平板', '相机', '数据线', '显示器', '蓝牙', '罗技', '机械键盘']],
    ['book', ['教材', '高数', '高等数学', '英语', '考研', '四六级', '课本', '小说', '资料', '笔记', '书籍', '图书', '同济']],
    ['clothing', ['衣服', '外套', '鞋', '包', '背包', '双肩包', '帽子', '裙子', '裤子', '卫衣']],
    ['home', ['台灯', '收纳', '椅子', '桌子', '床上用品', '水杯', '雨伞', '镜子', '插排', '宿舍']]
  ]
  const matched = rules.find(([, words]) => words.some((word) => text.indexOf(word.toLowerCase()) >= 0))
  return matched ? matched[0] : 'other'
}

module.exports = {
  API_BASE_URL,
  API_PREFIX,
  CLOUD_RUN_ENV,
  CLOUD_RUN_SERVICE,
  CLOUD_RUN_PUBLIC_BASE_URL,
  DEV_TEST_LOGIN_ENABLED,
  CURRENT_ENV,
  ENV_CONFIG,
  STORAGE_KEYS,
  PRODUCT_STATUS_TEXT,
  ORDER_STATUS_TEXT,
  CONDITION_OPTIONS,
  CAMPUS_OPTIONS,
  PRODUCT_CATEGORIES,
  getCategoryName,
  classifyProduct
}
