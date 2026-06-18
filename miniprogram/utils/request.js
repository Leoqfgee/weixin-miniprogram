const { API_BASE_URL, API_PREFIX, CLOUD_RUN_ENV, CLOUD_RUN_SERVICE } = require('./constants')
const { getToken, clearAuth } = require('./auth')

const STATUS_MESSAGE = {
  400: '请求参数不正确，请检查后重试',
  401: '登录已过期，请重新登录',
  403: '暂无权限操作',
  404: '内容不存在或已被删除',
  409: '当前状态已变化，请刷新后重试'
}

function buildTraceId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

function sanitizeMessage(message, fallback) {
  const text = String(message || '').trim()
  if (!text) return fallback
  if (/Traceback|SQL|Mongo|Exception|stack|KeyError|ValueError|TypeError/i.test(text)) {
    return fallback
  }
  return text.length > 30 ? text.slice(0, 30) : text
}

function extractErrorMessage(statusCode, payload) {
  const fallback = statusCode >= 500 ? '服务暂时不可用，请稍后重试' : (STATUS_MESSAGE[statusCode] || '请求失败，请稍后重试')
  const errors = payload && Array.isArray(payload.errors) ? payload.errors : []
  if (errors.length && errors[0] && errors[0].message) {
    return sanitizeMessage(errors[0].message, fallback)
  }
  return sanitizeMessage(payload && payload.message, fallback)
}

function showError(statusCode, payload, options) {
  if (options && options.silentError) return
  const message = extractErrorMessage(statusCode, payload)
  if (statusCode === 401) {
    clearAuth()
    wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
    wx.navigateTo({ url: '/pages/login/index' })
    return
  }
  wx.showToast({ title: message, icon: 'none' })
}

function request(options) {
  const token = getToken()
  const header = Object.assign(
    {
      'Content-Type': 'application/json',
      'X-Trace-Id': buildTraceId()
    },
    options.header || {}
  )
  if (token) {
    header.Authorization = `Bearer ${token}`
  }

  if (options.loading) {
    wx.showLoading({ title: options.loadingText || '加载中' })
  }

  return new Promise((resolve, reject) => {
    wx.cloud.callContainer({
      config: { env: CLOUD_RUN_ENV },
      path: `${API_PREFIX}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: Object.assign({ 'X-WX-SERVICE': CLOUD_RUN_SERVICE }, header),
      success(res) {
        const payload = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && payload.code === 0) {
          resolve(payload.data || {})
          return
        }
        showError(res.statusCode, payload, options)
        reject({ statusCode: res.statusCode, payload, message: extractErrorMessage(res.statusCode, payload) })
      },
      fail(err) {
        if (!options.silentError) {
          wx.showToast({ title: '网络异常，请检查网络后重试', icon: 'none' })
        }
        reject(err)
      },
      complete() {
        if (options.loading) {
          wx.hideLoading()
        }
      }
    })
  })
}

function uploadFile(options) {
  const token = getToken()
  const header = Object.assign({ 'X-Trace-Id': buildTraceId() }, options.header || {})
  if (token) {
    header.Authorization = `Bearer ${token}`
  }
  if (options.loading) {
    wx.showLoading({ title: options.loadingText || '上传中' })
  }
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${API_BASE_URL}${options.url}`,
      filePath: options.filePath,
      name: options.name || 'file',
      formData: options.formData || {},
      header,
      success(res) {
        let payload = {}
        try {
          payload = JSON.parse(res.data || '{}')
        } catch (err) {
          if (!options.silentError) wx.showToast({ title: '上传结果异常，请重试', icon: 'none' })
          reject(err)
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && payload.code === 0) {
          resolve(payload.data || {})
          return
        }
        showError(res.statusCode, payload, options)
        reject({ statusCode: res.statusCode, payload, message: extractErrorMessage(res.statusCode, payload) })
      },
      fail(err) {
        if (!options.silentError) wx.showToast({ title: '图片上传失败，请稍后重试', icon: 'none' })
        reject(err)
      },
      complete() {
        if (options.loading) {
          wx.hideLoading()
        }
      }
    })
  })
}

module.exports = {
  request,
  uploadFile,
  get(url, data, options) {
    return request(Object.assign({}, options || {}, { url, data, method: 'GET' }))
  },
  post(url, data, options) {
    return request(Object.assign({}, options || {}, { url, data, method: 'POST' }))
  },
  put(url, data, options) {
    return request(Object.assign({}, options || {}, { url, data, method: 'PUT' }))
  },
  del(url, data, options) {
    return request(Object.assign({}, options || {}, { url, data, method: 'DELETE' }))
  }
}
