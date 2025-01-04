const excelParser = require('../../utils/excel-parser.js')

Page({
  data: {
    excelData: null,
    headers: [],
    displaySettings: null
  },

  onLoad: function() {
    const app = getApp()
    this.setData({
      displaySettings: app.globalData.displaySettings
    })
  },

  chooseFile: function() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['xlsx', 'xls', 'csv'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].path
        this.parseExcelFile(tempFilePath)
      }
    })
  },

  parseExcelFile: function(filePath) {
    const fileData = wx.getFileSystemManager().readFileSync(filePath)
    const result = excelParser.parseExcelFile(fileData)
    
    if (result.success) {
      this.setData({
        excelData: result.data,
        headers: result.headers
      })
      getApp().globalData.excelData = result.data
    } else {
      wx.showToast({
        title: '解析失败',
        icon: 'none'
      })
    }
  },

  navigateToSettings: function() {
    wx.navigateTo({
      url: '/pages/settings/settings'
    })
  }
})
