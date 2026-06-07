const api = require('../../../utils/request')
const { getUser, requireLogin } = require('../../../utils/auth')
const { refreshUnreadBadge } = require('../../../utils/unread')

function displayTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).replace('T', ' ').slice(0, 16)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

Page({
  data: {
    conversationId: '',
    receiverId: '',
    productId: '',
    product: {},
    messages: [],
    content: '',
    currentUserId: '',
    showEmoji: false,
    showPlus: false,
    voiceMode: false,
    recording: false,
    supportMode: false,
    emojis: ['😀', '😄', '😂', '🥰', '😎', '🤔', '😭', '😅', '👍', '👏', '🙏', '🎉', '❤️', '🔥', '✅', '🌟'],
    scrollIntoView: ''
  },
  onLoad(options) {
    requireLogin()
    const user = getUser() || {}
    this.setData({
      conversationId: options.conversation_id || '',
      receiverId: options.receiver_id || '',
      productId: options.product_id || '',
      currentUserId: user.id || '',
      supportMode: options.support === '1',
      product: {
        title: options.product_title ? decodeURIComponent(options.product_title) : '',
        price: options.product_price || '',
        cover_image: options.product_cover ? decodeURIComponent(options.product_cover) : ''
      }
    })
    if (options.support === '1') wx.setNavigationBarTitle({ title: '平台客服' })
    this.initRecorder()
    this.loadMessages()
  },
  initRecorder() {
    if (!wx.getRecorderManager) return
    this.recorder = wx.getRecorderManager()
    this.recorder.onStop((res) => {
      this.setData({ recording: false })
      api.uploadFile({
        url: '/files/upload',
        filePath: res.tempFilePath,
        formData: { usage: 'chat' },
        loading: true
      }).then((data) => this.sendMessage({ message_type: 'voice', image_url: data.url, content: '[语音]' }))
    })
  },
  onInput(event) {
    this.setData({ content: event.detail.value })
  },
  loadMessages() {
    if (!this.data.conversationId) return
    api.get(`/messages/${this.data.conversationId}`).then((data) => {
      let previous = 0
      const messages = (data.items || []).map((item) => {
        const stamp = new Date(item.created_at).getTime()
        const result = Object.assign({}, item, {
          mine: item.is_mine || item.sender_id === this.data.currentUserId,
          show_time: !previous || stamp - previous > 5 * 60 * 1000,
          time_text: displayTime(item.created_at)
        })
        previous = stamp
        return result
      })
      this.setData({ messages, scrollIntoView: messages.length ? `msg-${messages[messages.length - 1].id}` : '' })
      refreshUnreadBadge()
    })
  },
  sendText() {
    const content = this.data.content.trim()
    if (content) this.sendMessage({ message_type: 'text', content })
  },
  toggleVoice() {
    this.setData({ voiceMode: !this.data.voiceMode, showEmoji: false, showPlus: false })
  },
  toggleEmoji() {
    this.setData({ showEmoji: !this.data.showEmoji, showPlus: false })
  },
  togglePlus() {
    this.setData({ showPlus: !this.data.showPlus, showEmoji: false })
  },
  addEmoji(event) {
    this.setData({ content: this.data.content + event.currentTarget.dataset.value })
  },
  startVoice() {
    if (!this.recorder) return
    this.setData({ recording: true })
    this.recorder.start({ duration: 60000, format: 'mp3' })
  },
  stopVoice() {
    if (this.recorder && this.data.recording) this.recorder.stop()
  },
  chooseMedia(event) {
    const sourceType = event.currentTarget.dataset.source || 'album'
    wx.chooseMedia({
      count: 1,
      mediaType: ['image', 'video'],
      sourceType: [sourceType],
      success: (res) => {
        const file = res.tempFiles[0]
        const type = res.type === 'video' ? 'video' : 'image'
        api.uploadFile({
          url: '/files/upload',
          filePath: file.tempFilePath,
          formData: { usage: 'chat' },
          loading: true
        }).then((data) => this.sendMessage({ message_type: type, image_url: data.url, content: type === 'video' ? '[视频]' : '[图片]' }))
      }
    })
  },
  viewReview(event) {
    wx.navigateTo({ url: `/pages/review/detail/index?id=${event.currentTarget.dataset.id}` })
  },
  previewImage(event) {
    wx.previewImage({ urls: [event.currentTarget.dataset.url] })
  },
  viewProduct() {
    if (this.data.productId) {
      wx.navigateTo({ url: `/pages/product/detail/index?id=${this.data.productId}` })
    }
  },
  viewUser(event) {
    const userId = event.currentTarget.dataset.id
    if (userId) {
      wx.navigateTo({ url: `/pages/profile/home/index?id=${userId}` })
    }
  },
  sendMessage(extra) {
    if (!this.data.receiverId) {
      wx.showToast({ title: '缺少收信人', icon: 'none' })
      return
    }
    api.post('/messages', Object.assign({
      receiver_id: this.data.receiverId,
      product_id: this.data.productId
    }, extra), { loading: true }).then((message) => {
      this.setData({
        content: '',
        conversationId: this.data.conversationId || message.conversation_id,
        showEmoji: false,
        showPlus: false
      })
      this.loadMessages()
    })
  }
})
