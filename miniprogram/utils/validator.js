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
  if (!required(form.title) || form.title.length < 2 || form.title.length > 50) {
    errors.title = '标题需为 2-50 字'
  }
  if (!validatePrice(form.price)) {
    errors.price = '价格必须大于 0'
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

module.exports = {
  required,
  validatePrice,
  validateStock,
  validateImages,
  validateProductForm
}
