const app = getApp()
const { isFileSupported, parseExcelFile } = require('../../utils/excel-parser')

Page({
  data: {
    tableData: null,
    displaySettings: {},
    undoStack: [],
    redoStack: [],
    hasUploadedFile: false,
    isProcessing: false,
    errorMessage: '',
    studentInfo: null,
    displayAttributes: [],
    fixedAttributes: ['学校名称', '专业名称', '学校代码', '专业代码', '位次差'],
    selectedRowIndex: -1,
    moveToVisible: false,
    moveToRowNumber: ''
  },

  onLoad() {
    // Load display settings
    const displaySettings = wx.getStorageSync('displaySettings') || {};
    const selectedAttributes = displaySettings.attributes || [];
    
    // Check if we have any previously loaded data
    if (app.globalData.tableData) {
      this.setData({
        tableData: app.globalData.tableData,
        hasUploadedFile: true,
        displayAttributes: selectedAttributes
      });
    }
  },

  // Update display when settings change
  updateDisplay() {
    const displaySettings = wx.getStorageSync('displaySettings') || {};
    const selectedAttributes = displaySettings.attributes || [];
    
    this.setData({
      displayAttributes: selectedAttributes
    });
  },

  chooseFile() {
    const that = this;
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['xlsx', 'xls', 'csv'],
      success(res) {
        const tempFilePath = res.tempFiles[0];
        that.handleFileUpload(tempFilePath);
      },
      fail(error) {
        console.error('File selection failed:', error);
        that.setData({
          errorMessage: '文件选择失败，请重试'
        });
      }
    });
  },

  async handleFileUpload(file) {
    if (!isFileSupported(file.name)) {
      this.setData({
        errorMessage: '不支持的文件格式。请上传 .xlsx, .xls 或 .csv 文件'
      });
      return;
    }

    this.setData({ isProcessing: true, errorMessage: '' });

    try {
      // Read file as ArrayBuffer
      const fileContent = await new Promise((resolve, reject) => {
        wx.getFileSystemManager().readFile({
          filePath: file.path,
          encoding: 'binary',
          success: res => resolve(res.data),
          fail: err => reject(err)
        });
      });

      const result = await parseExcelFile(fileContent);
      
      // Get all attributes from the first row
      const allAttributes = result.rows && result.rows.length > 0 ? Object.keys(result.rows[0]) : [];
      
      // Filter out fixed attributes to get dynamic ones
      const dynamicAttributes = allAttributes.filter(attr => !this.data.fixedAttributes.includes(attr));
      
      // Store in global data with dynamic attributes
      app.globalData.tableData = {
        ...result,
        dynamicAttributes
      };
      
      this.setData({
        tableData: result,
        hasUploadedFile: true,
        isProcessing: false,
        errorMessage: '',
        displayAttributes: dynamicAttributes
      });

      // Navigate to settings page for attribute configuration
      wx.navigateTo({
        url: '/pages/settings/settings',
        success: () => {
          wx.showToast({
            title: '请配置显示设置',
            icon: 'none',
            duration: 2000
          });
        }
      });
    } catch (error) {
      console.error('File processing error:', error);
      this.setData({
        errorMessage: error.message || '文件处理失败，请重试',
        isProcessing: false
      });
    }
  },

  // Save current state for undo/redo
  saveState() {
    const currentState = JSON.stringify({
      tableData: this.data.tableData,
      selectedRowIndex: this.data.selectedRowIndex
    });
    const undoStack = [...this.data.undoStack];
    undoStack.push(currentState);
    this.setData({ 
      undoStack,
      redoStack: [] // Clear redo stack when new action is performed
    });
  },

  // Undo last action
  undo() {
    if (this.data.undoStack.length === 0) {
      wx.showToast({
        title: '没有可撤销的操作',
        icon: 'none'
      });
      return;
    }

    const undoStack = [...this.data.undoStack];
    const redoStack = [...this.data.redoStack];
    const currentState = JSON.stringify({
      tableData: this.data.tableData,
      selectedRowIndex: this.data.selectedRowIndex
    });
    redoStack.push(currentState);

    const previousState = JSON.parse(undoStack.pop());
    this.setData({
      tableData: previousState.tableData,
      selectedRowIndex: previousState.selectedRowIndex,
      undoStack,
      redoStack
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Redo last undone action
  redo() {
    if (this.data.redoStack.length === 0) {
      wx.showToast({
        title: '没有可重做的操作',
        icon: 'none'
      });
      return;
    }

    const undoStack = [...this.data.undoStack];
    const redoStack = [...this.data.redoStack];
    const currentState = JSON.stringify({
      tableData: this.data.tableData,
      selectedRowIndex: this.data.selectedRowIndex
    });
    undoStack.push(currentState);

    const nextState = JSON.parse(redoStack.pop());
    this.setData({
      tableData: nextState.tableData,
      selectedRowIndex: nextState.selectedRowIndex,
      undoStack,
      redoStack
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Select a row
  selectRow(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ selectedRowIndex: index });
  },

  // Delete selected row
  deleteRow() {
    if (this.data.selectedRowIndex === -1) {
      wx.showToast({
        title: '请先选择一行',
        icon: 'none'
      });
      return;
    }

    this.saveState();
    const newRows = [...this.data.tableData.rows];
    newRows.splice(this.data.selectedRowIndex, 1);
    
    this.setData({
      'tableData.rows': newRows,
      'tableData.totalRows': newRows.length,
      selectedRowIndex: -1
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Move row up
  moveRowUp() {
    if (this.data.selectedRowIndex <= 0) {
      wx.showToast({
        title: '已经是第一行',
        icon: 'none'
      });
      return;
    }

    this.saveState();
    const newRows = [...this.data.tableData.rows];
    const temp = newRows[this.data.selectedRowIndex - 1];
    newRows[this.data.selectedRowIndex - 1] = newRows[this.data.selectedRowIndex];
    newRows[this.data.selectedRowIndex] = temp;

    this.setData({
      'tableData.rows': newRows,
      selectedRowIndex: this.data.selectedRowIndex - 1
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Move row down
  moveRowDown() {
    if (this.data.selectedRowIndex === -1 || 
        this.data.selectedRowIndex >= this.data.tableData.rows.length - 1) {
      wx.showToast({
        title: '已经是最后一行',
        icon: 'none'
      });
      return;
    }

    this.saveState();
    const newRows = [...this.data.tableData.rows];
    const temp = newRows[this.data.selectedRowIndex + 1];
    newRows[this.data.selectedRowIndex + 1] = newRows[this.data.selectedRowIndex];
    newRows[this.data.selectedRowIndex] = temp;

    this.setData({
      'tableData.rows': newRows,
      selectedRowIndex: this.data.selectedRowIndex + 1
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Show move to dialog
  showMoveToDialog() {
    if (this.data.selectedRowIndex === -1) {
      wx.showToast({
        title: '请先选择一行',
        icon: 'none'
      });
      return;
    }
    this.setData({ moveToVisible: true });
  },

  // Handle move to row input
  handleMoveToInput(e) {
    this.setData({ moveToRowNumber: e.detail.value });
  },

  // Move row to specific position
  moveRowTo() {
    const targetRow = parseInt(this.data.moveToRowNumber) - 1;
    if (isNaN(targetRow) || targetRow < 0 || 
        targetRow >= this.data.tableData.rows.length) {
      wx.showToast({
        title: '请输入有效的行号',
        icon: 'none'
      });
      return;
    }

    this.saveState();
    const newRows = [...this.data.tableData.rows];
    const movedRow = newRows.splice(this.data.selectedRowIndex, 1)[0];
    newRows.splice(targetRow, 0, movedRow);

    this.setData({
      'tableData.rows': newRows,
      selectedRowIndex: targetRow,
      moveToVisible: false,
      moveToRowNumber: ''
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Close move to dialog
  closeMoveToDialog() {
    this.setData({
      moveToVisible: false,
      moveToRowNumber: ''
    });
  },

  // Stop event propagation for dialog content
  stopPropagation(e) {
    // Prevent click from reaching the parent
    e.stopPropagation();
  },

  // Mark row with purple background
  markRow() {
    if (this.data.selectedRowIndex === -1) {
      wx.showToast({
        title: '请先选择一行',
        icon: 'none'
      });
      return;
    }

    this.saveState();
    const newRows = [...this.data.tableData.rows];
    const row = newRows[this.data.selectedRowIndex];
    
    // Update background color for all cells in the row
    Object.keys(row).forEach(key => {
      if (row[key].style) {
        row[key].style.backgroundColor = '#E6E6FA'; // Light purple
      }
    });

    this.setData({
      'tableData.rows': newRows
    });

    // Update Excel file
    app.globalData.tableData = this.data.tableData;
  },

  // Save and share
  saveAndShare() {
    if (!this.data.tableData) {
      wx.showToast({
        title: '没有可保存的数据',
        icon: 'none'
      });
      return;
    }

    wx.showLoading({
      title: '保存中...'
    });

    try {
      // Update Excel file in app.globalData
      app.globalData.tableData = this.data.tableData;

      // Create a temporary file path
      const tempFilePath = `${wx.env.USER_DATA_PATH}/temp.xlsx`;
      
      // Save the file
      wx.getFileSystemManager().writeFile({
        filePath: tempFilePath,
        data: app.globalData.originalExcelData, // Use original Excel data format
        encoding: 'binary',
        success: () => {
          wx.hideLoading();
          // Share the file
          wx.shareFileMessage({
            filePath: tempFilePath,
            success: () => {
              wx.showToast({
                title: '分享成功',
                icon: 'success'
              });
            },
            fail: (err) => {
              console.error('Share failed:', err);
              wx.showToast({
                title: '分享失败',
                icon: 'none'
              });
            }
          });
        },
        fail: (err) => {
          console.error('Save failed:', err);
          wx.hideLoading();
          wx.showToast({
            title: '保存失败',
            icon: 'none'
          });
        }
      });
    } catch (err) {
      console.error('Save and share error:', err);
      wx.hideLoading();
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      });
    }
  }
})
