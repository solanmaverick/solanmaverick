Page({
  data: {
    attributes: []
  },

  onLoad: function() {
    const app = getApp()
    const settings = app.globalData.displaySettings || this.getDefaultSettings()
    this.setData({ attributes: settings })
  },

  getDefaultSettings: function() {
    const excelData = getApp().globalData.excelData
    if (!excelData || !excelData.headers) return []
    
    return excelData.headers.map(header => ({
      name: header,
      visible: true
    }))
  },

  toggleAttribute: function(e) {
    const index = e.currentTarget.dataset.index
    const attributes = this.data.attributes
    attributes[index].visible = !attributes[index].visible
    this.setData({ attributes })
  },

  saveSettings: function() {
    getApp().globalData.displaySettings = this.data.attributes
    wx.navigateBack()
  }
})
