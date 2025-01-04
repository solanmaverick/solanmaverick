Page({
  data: {
    availableAttributes: [],
    selectedAttributes: [],
    fixedAttributes: ['学校名称', '专业名称', '学校代码', '专业代码', '位次差']
  },

  onLoad() {
    const app = getApp()
    // Load all available attributes except fixed ones
    this.setData({
      availableAttributes: this.getAvailableAttributes(),
      selectedAttributes: wx.getStorageSync('selectedAttributes') || []
    })
  },

  getAvailableAttributes() {
    const app = getApp();
    if (!app.globalData.tableData || !app.globalData.tableData.rows || !app.globalData.tableData.rows[0]) {
      return [];
    }
    
    // Get all attributes from the first row
    const allAttributes = Object.keys(app.globalData.tableData.rows[0]);
    
    // Filter out fixed attributes
    return allAttributes.filter(attr => !this.data.fixedAttributes.includes(attr));
  },

  toggleAttribute(e) {
    const { attribute } = e.currentTarget.dataset;
    const { selectedAttributes } = this.data;
    const index = selectedAttributes.indexOf(attribute);
    
    if (index === -1) {
      selectedAttributes.push(attribute);
    } else {
      selectedAttributes.splice(index, 1);
    }
    
    this.setData({ selectedAttributes });
    
    // Save settings
    const settings = {
      attributes: selectedAttributes
    };
    wx.setStorageSync('displaySettings', settings);
    
    // Update main page
    const pages = getCurrentPages();
    const prevPage = pages[pages.length - 2];
    if (prevPage) {
      prevPage.updateDisplay();
    }
    
    wx.showToast({
      title: '设置已更新',
      icon: 'success',
      duration: 1500
    });
  },

  moveAttributeUp(e) {
    const { index } = e.currentTarget.dataset;
    if (index > 0) {
      const { selectedAttributes } = this.data;
      const temp = selectedAttributes[index];
      selectedAttributes[index] = selectedAttributes[index - 1];
      selectedAttributes[index - 1] = temp;
      
      this.setData({ selectedAttributes });
      
      // Save settings
      const settings = {
        attributes: selectedAttributes
      };
      wx.setStorageSync('displaySettings', settings);
      
      // Update main page
      const pages = getCurrentPages();
      const prevPage = pages[pages.length - 2];
      if (prevPage) {
        prevPage.updateDisplay();
      }
      
      wx.showToast({
        title: '顺序已更新',
        icon: 'success',
        duration: 1500
      });
    } else {
      wx.showToast({
        title: '已经是第一个',
        icon: 'none',
        duration: 1500
      });
    }
  },

  moveAttributeDown(e) {
    const { index } = e.currentTarget.dataset;
    const { selectedAttributes } = this.data;
    if (index < selectedAttributes.length - 1) {
      const temp = selectedAttributes[index];
      selectedAttributes[index] = selectedAttributes[index + 1];
      selectedAttributes[index + 1] = temp;
      
      this.setData({ selectedAttributes });
      
      // Save settings
      const settings = {
        attributes: selectedAttributes
      };
      wx.setStorageSync('displaySettings', settings);
      
      // Update main page
      const pages = getCurrentPages();
      const prevPage = pages[pages.length - 2];
      if (prevPage) {
        prevPage.updateDisplay();
      }
      
      wx.showToast({
        title: '顺序已更新',
        icon: 'success',
        duration: 1500
      });
    } else {
      wx.showToast({
        title: '已经是最后一个',
        icon: 'none',
        duration: 1500
      });
    }
  }
})
