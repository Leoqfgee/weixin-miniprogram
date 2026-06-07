const { API_BASE_URL, API_PREFIX, CLOUD_RUN_ENV, CLOUD_RUN_SERVICE } = require('./constants')
const { getToken, clearAuth } = require('./auth')

function buildTraceId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

function showError(statusCode, payload) {
  const message = payload && payload.message ? payload.message : '请求失败'
  if (statusCode === 401) {
    clearAuth()
    wx.showToast({ title: '登录已过期', icon: 'none' })
    wx.navigateTo({ url: '/pages/login/index' })
    return
  }
  if (statusCode === 403) {
    wx.showToast({ title: message || '无权限操作', icon: 'none' })
    return
  }
  if (statusCode === 404) {
    wx.showToast({ title: message || '资源不存在', icon: 'none' })
    return
  }
  if (statusCode === 409) {
    wx.showToast({ title: message || '状态已变化，请刷新', icon: 'none' })
    return
  }
  if (statusCode >= 500) {
    wx.showToast({ title: '服务器异常', icon: 'none' })
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
      config: {
        env: CLOUD_RUN_ENV
      },
      path: `${API_PREFIX}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: Object.assign(
        {
          'X-WX-SERVICE': CLOUD_RUN_SERVICE
        },
        header
      ),
      success(res) {
        const payload = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && payload.code === 0) {
          resolve(payload.data || {})
          return
        }
        showError(res.statusCode, payload)
        reject({ statusCode: res.statusCode, payload })
      },
      fail(err) {
        wx.showToast({ title: '连接后端失败，请检查网络和 API 地址', icon: 'none' })
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
          wx.showToast({ title: '上传响应解析失败', icon: 'none' })
          reject(err)
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && payload.code === 0) {
          resolve(payload.data || {})
          return
        }
        showError(res.statusCode, payload)
        reject({ statusCode: res.statusCode, payload })
      },
      fail(err) {
        wx.showToast({ title: '图片上传失败', icon: 'none' })
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
