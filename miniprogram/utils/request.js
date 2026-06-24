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

  let loadingVisible = false
  if (options.loading) {
    wx.showLoading({ title: options.loadingText || '加载中' })
    loadingVisible = true
  }

  const hideLoadingIfNeeded = () => {
    if (loadingVisible) {
      wx.hideLoading()
      loadingVisible = false
    }
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
        hideLoadingIfNeeded()
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
        hideLoadingIfNeeded()
      }
    })
  })
}

function uploadFile(options) {
  const initialMimeType = options.mimeType || mimeFromPath(options.filePath)
  if (options.useMultipart !== true && isImageMime(initialMimeType)) {
    const formData = options.formData || {}
    const usage = formData.usage || options.usage || 'product'
    const baseOptions = {
      url: options.base64Url || '/files/upload-base64',
      filePath: options.filePath,
      filename: options.filename || filenameFromPath(options.filePath),
      mimeType: initialMimeType,
      usage,
      loading: options.loading,
      loadingText: options.loadingText || '上传中',
      silentError: true
    }
    return prepareUploadFilePath(options.filePath, baseOptions.mimeType)
      .then((filePath) => uploadImageBase64(Object.assign({}, baseOptions, {
        filePath,
        filename: options.filename || filenameFromPath(filePath)
      })))
      .catch((base64Error) => uploadCloudFile(Object.assign({}, options, {
        usage,
        originalError: base64Error
      })))
      .catch((err) => {
        if (!options.silentError) wx.showToast({ title: '图片上传失败，请稍后重试', icon: 'none' })
        throw err
      })
  }
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
        hideLoadingIfNeeded()
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

function prepareUploadFilePath(filePath, mimeType) {
  if (!isImageMime(mimeType) || !wx.compressImage) {
    return Promise.resolve(filePath)
  }
  return new Promise((resolve) => {
    wx.compressImage({
      src: filePath,
      quality: 65,
      success(res) {
        resolve(res.tempFilePath || filePath)
      },
      fail() {
        resolve(filePath)
      }
    })
  })
}

function uploadCloudFile(options) {
  if (!wx.cloud || !wx.cloud.uploadFile) {
    return Promise.reject(options.originalError || new Error('cloud upload unavailable'))
  }
  const filePath = options.filePath
  const usage = options.usage || 'product'
  const cloudPath = `${usage}/${Date.now()}-${Math.random().toString(36).slice(2, 10)}.${extensionFromPath(filePath)}`
  return new Promise((resolve, reject) => {
    wx.cloud.uploadFile({
      cloudPath,
      filePath,
      success(res) {
        const fileID = res.fileID || ''
        if (!fileID) {
          reject(options.originalError || new Error('empty cloud file id'))
          return
        }
        resolve({
          id: fileID,
          url: fileID,
          object_key: cloudPath,
          relative_path: cloudPath,
          storage_backend: 'cloudbase',
          usage
        })
      },
      fail(err) {
        reject(err || options.originalError)
      }
    })
  })
}

function uploadImageBase64(options) {
  const filePath = options.filePath
  const fs = wx.getFileSystemManager()
  return new Promise((resolve, reject) => {
    fs.readFile({
      filePath,
      encoding: 'base64',
      success(res) {
        request({
          url: options.url || '/files/upload-base64',
          method: 'POST',
          data: {
            usage: options.usage || 'avatar',
            filename: options.filename || filenameFromPath(filePath),
            mime_type: options.mimeType || mimeFromPath(filePath),
            content_base64: res.data
          },
          loading: options.loading,
          loadingText: options.loadingText,
          silentError: options.silentError
        }).then(resolve).catch(reject)
      },
      fail(err) {
        if (!options.silentError) wx.showToast({ title: '图片读取失败，请重试', icon: 'none' })
        reject(err)
      }
    })
  })
}

function filenameFromPath(filePath) {
  const value = String(filePath || '')
  const clean = value.split('?')[0]
  const name = clean.split('/').pop() || 'avatar.jpg'
  return name.indexOf('.') >= 0 ? name : 'avatar.jpg'
}

function mimeFromPath(filePath) {
  const filename = filenameFromPath(filePath).toLowerCase()
  if (filename.endsWith('.png')) return 'image/png'
  if (filename.endsWith('.webp')) return 'image/webp'
  if (filename.endsWith('.gif')) return 'image/gif'
  if (filename.endsWith('.mp4') || filename.endsWith('.m4v')) return 'video/mp4'
  if (filename.endsWith('.mov')) return 'video/quicktime'
  if (filename.endsWith('.mp3')) return 'audio/mpeg'
  if (filename.endsWith('.aac')) return 'audio/aac'
  if (filename.endsWith('.wav')) return 'audio/wav'
  return 'image/jpeg'
}

function extensionFromPath(filePath) {
  const filename = filenameFromPath(filePath).toLowerCase()
  if (filename.endsWith('.png')) return 'png'
  if (filename.endsWith('.webp')) return 'webp'
  if (filename.endsWith('.gif')) return 'gif'
  return 'jpg'
}

function isImageMime(mimeType) {
  return String(mimeType || '').indexOf('image/') === 0
}

module.exports = {
  request,
  uploadFile,
  uploadImageBase64,
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
