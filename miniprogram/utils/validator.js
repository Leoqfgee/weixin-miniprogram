function required(value) {
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return value !== undefined && value !== null && String(value).trim() !== ''
}

function validatePrice(value) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0
}

function validateStock(value) {
  const num = Number(value)
  return Number.isInteger(num) && num >= 0
}

function validateImages(images, maxCount) {
  return Array.isArray(images) && images.length <= (maxCount || 9)
}

function validateProductForm(form) {
  const errors = {}
  if (!required(form.title)) {
    errors.title = '标题不能为空'
  } else if (String(form.title).trim().length < 2 || String(form.title).trim().length > 50) {
    errors.title = '标题需为 2-50 字'
  }
  if (!required(form.price)) {
    errors.price = '价格不能为空'
  } else if (!validatePrice(form.price)) {
    errors.price = '价格格式不正确'
  }
  if (!required(form.description)) {
    errors.description = '商品描述不能为空'
  }
  if (!validateStock(Number(form.stock))) {
    errors.stock = '库存必须是非负整数'
  }
  if (!validateImages(form.images, 9)) {
    errors.images = '图片最多 9 张'
  }
  return {
    valid: Object.keys(errors).length === 0,
    errors
  }
}

function firstError(errors, fallback) {
  const keys = Object.keys(errors || {})
  return keys.length ? errors[keys[0]] : fallback
}

module.exports = {
  required,
  validatePrice,
  validateStock,
  validateImages,
  validateProductForm,
  firstError
}
