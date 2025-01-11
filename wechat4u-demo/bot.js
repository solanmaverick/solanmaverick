const Wechat4u = require('wechat4u')
const fs = require('fs-extra')
const dayjs = require('dayjs')
const path = require('path')
const summarizer = require('./summarizer')

// Ensure required directories exist
fs.ensureDirSync('logs')
fs.ensureDirSync('media')
fs.ensureDirSync('summaries')

// Initialize bot with state management
const STATE_FILE = 'wechat-state.json'
let bot

function initBot() {
  try {
    // Try to load existing state
    if (fs.existsSync(STATE_FILE)) {
      console.log('Debug: Loading existing state...')
      bot = new Wechat4u(require(`./${STATE_FILE}`))
    } else {
      console.log('Debug: Creating new bot instance...')
      bot = new Wechat4u()
    }

    // Load configuration
    const CONFIG_FILE = 'config.json'
    let config = {
      monitoredGroups: [],
      summaryTime: '23:59'
    }

    if (fs.existsSync(CONFIG_FILE)) {
      config = fs.readJsonSync(CONFIG_FILE)
    } else {
      fs.writeJsonSync(CONFIG_FILE, config, { spaces: 2 })
    }

    return bot
  } catch (error) {
    console.error('Error initializing bot:', error)
    throw error
  }
}

function setupBotEvents(bot) {
  // Listen for scan event (QR Code)
  bot.on('scan', async ({url}) => {
    try {
      // Clear QR timeout since we received the event
      clearTimeout(qrTimeout)
      
      console.log('\n==================================')
      console.log('Debug: Received scan event')
      
      // Save QR code as image file
      const qr = require('qrcode')
      const qrPath = 'QR.png'
      await qr.toFile(qrPath, url)
      console.log(`QR Code saved as ${qrPath}`)
      console.log('Scan QR Code to login')
      console.log('==================================\n')
      
      // Log the URL to a file for debugging
      fs.appendFileSync('logs/qr_urls.log', `${new Date().toISOString()}: ${url}\n`)
    } catch (error) {
      console.error('Error generating QR code:', error)
    }
  })

  // Listen for login
  bot.on('login', () => {
    console.log('\n==================================')
    console.log('Successfully logged in!')
    console.log('==================================\n')
    
    // Save bot state
    fs.writeFileSync(STATE_FILE, JSON.stringify(bot.botData))
    console.log('Debug: Bot state saved')
    
    // Update group list after login
    updateGroupList()
  })

  // Listen for logout
  bot.on('logout', () => {
    console.log('\n==================================')
    console.log('Logged out!')
    console.log('==================================\n')
    
    // Clear state file
    if (fs.existsSync(STATE_FILE)) {
      fs.unlinkSync(STATE_FILE)
      console.log('Debug: Bot state cleared')
    }
  })

  // Listen for error events
  bot.on('error', (err) => {
    console.error('Bot error:', err)
    // Try to reinitialize on error
    setTimeout(() => {
      console.log('Debug: Attempting to recover from error...')
      bot = initBot()
      setupBotEvents(bot)
      bot.start()
    }, 5000)
  })

  // Listen for state change
  bot.on('state-change', state => {
    console.log('Debug: Bot state changed to', state)
  })

  return bot
}

// Listen for messages
bot.on('message', (msg) => {
  handleMessage(msg)
})

// Update group list
function updateGroupList() {
  try {
    const groups = bot.contacts
    const groupList = []
    
    for (const [id, contact] of Object.entries(groups)) {
      if (contact.UserName.startsWith('@@')) {
        groupList.push({
          id: contact.UserName,
          name: contact.NickName || 'Unknown Group'
        })
      }
    }
    
    console.log('\nAvailable Groups:')
    groupList.forEach(group => {
      const monitored = config.monitoredGroups.includes(group.id) ? '✓' : ' '
      console.log(`[${monitored}] ${group.name} (ID: ${group.id})`)
    })
    console.log('\n')
    
  } catch (error) {
    console.error('Error updating group list:', error)
  }
}

// Handle incoming messages
function handleMessage(msg) {
  try {
    // Only process group messages from monitored groups
    if (msg.FromUserName.startsWith('@@') && config.monitoredGroups.includes(msg.FromUserName)) {
      const timestamp = dayjs().format('YYYY-MM-DD HH:mm:ss')
      const sender = msg.ActualNickName || 'Unknown'
      const groupName = bot.contacts[msg.FromUserName].NickName || 'Unknown Group'
      
      // Prepare message content based on type
      let content = ''
      if (msg.MsgType === bot.CONF.MSGTYPE_TEXT) {
        content = msg.Content
      } else if (msg.MsgType === bot.CONF.MSGTYPE_IMAGE) {
        const filename = `media/${dayjs().format('YYYYMMDD_HHmmss')}_${msg.MsgId}.jpg`
        bot.getMsgImg(msg.MsgId).pipe(fs.createWriteStream(filename))
        content = `[Image] Saved as: ${filename}`
      } else {
        content = `[Message Type: ${msg.MsgType}]`
      }
      
      // Log message
      const logEntry = `${timestamp} - ${sender}: ${content}\n`
      const dateStr = dayjs().format('YYYY-MM-DD')
      const logFile = `logs/group_${msg.FromUserName}_${dateStr}.log`
      
      fs.appendFileSync(logFile, logEntry)
      console.log(`[${groupName}] ${logEntry}`)
    }
  } catch (error) {
    console.error('Error handling message:', error)
  }
}

// Command handler for filehelper
bot.on('message', (msg) => {
  if (msg.ToUserName === 'filehelper') {
    handleCommand(msg.Content.trim())
  }
})

// Handle bot commands
function handleCommand(command) {
  try {
    if (command === '/list') {
      // List all available groups
      const groups = Object.entries(bot.contacts)
        .filter(([id]) => id.startsWith('@@'))
        .map(([id, contact]) => ({
          id,
          name: contact.NickName || 'Unknown Group'
        }))

      let response = '📋 Available Groups:\n'
      groups.forEach(group => {
        const monitored = config.monitoredGroups.includes(group.id) ? '✓' : ' '
        response += `[${monitored}] ${group.name}\n    ID: ${group.id}\n`
      })
      response += `\nCurrently monitoring ${config.monitoredGroups.length} groups`
      
      bot.sendMsg(response, 'filehelper')
    }
    else if (command.startsWith('/monitor ')) {
      const groupId = command.slice(9).trim()
      if (!groupId.startsWith('@@')) {
        bot.sendMsg('❌ Invalid group ID. Use /list to see available groups.', 'filehelper')
        return
      }

      if (config.monitoredGroups.includes(groupId)) {
        bot.sendMsg('⚠️ This group is already being monitored.', 'filehelper')
        return
      }

      const group = bot.contacts[groupId]
      if (!group) {
        bot.sendMsg('❌ Group not found. Use /list to see available groups.', 'filehelper')
        return
      }

      config.monitoredGroups.push(groupId)
      fs.writeJsonSync(CONFIG_FILE, config, { spaces: 2 })
      bot.sendMsg(`✅ Now monitoring: ${group.NickName}`, 'filehelper')
    }
    else if (command.startsWith('/unmonitor ')) {
      const groupId = command.slice(11).trim()
      const index = config.monitoredGroups.indexOf(groupId)
      
      if (index === -1) {
        bot.sendMsg('⚠️ This group is not being monitored.', 'filehelper')
        return
      }

      const group = bot.contacts[groupId]
      config.monitoredGroups.splice(index, 1)
      fs.writeJsonSync(CONFIG_FILE, config, { spaces: 2 })
      bot.sendMsg(`❌ Stopped monitoring: ${group ? group.NickName : groupId}`, 'filehelper')
    }
    else if (command === '/help') {
      const help = `
📱 WeChat Monitor Commands:

/list
    List all available groups and their monitoring status

/monitor [group_id]
    Start monitoring a specific group

/unmonitor [group_id]
    Stop monitoring a specific group

/summary [group_id]
    Generate summary for a specific group (last 24 hours)

/help
    Show this help message
`
      bot.sendMsg(help, 'filehelper')
    }
    else if (command.startsWith('/summary ')) {
      const groupId = command.slice(9).trim()
      if (!config.monitoredGroups.includes(groupId)) {
        bot.sendMsg('❌ This group is not being monitored.', 'filehelper')
        return
      }

      const dateStr = dayjs().format('YYYY-MM-DD')
      summarizer.generateGroupSummary(groupId, dateStr)
        .then(() => {
          const summaryFile = path.join('summaries', `summary_${groupId}_${dateStr}.txt`)
          if (fs.existsSync(summaryFile)) {
            const summary = fs.readFileSync(summaryFile, 'utf8')
            bot.sendMsg(summary, 'filehelper')
          } else {
            bot.sendMsg('❌ No summary available for today.', 'filehelper')
          }
        })
        .catch(error => {
          console.error('Error generating summary:', error)
          bot.sendMsg('❌ Error generating summary.', 'filehelper')
        })
    }
  } catch (error) {
    console.error('Error handling command:', error)
    bot.sendMsg('❌ Error processing command. Please try again.', 'filehelper')
  }
}

// Error handling for uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error)
  // Don't exit, try to recover
  setTimeout(() => {
    console.log('Debug: Attempting to recover from uncaught exception...')
    bot = initBot()
    setupBotEvents(bot)
    bot.start()
  }, 5000)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason)
  // Don't exit, try to recover
  setTimeout(() => {
    console.log('Debug: Attempting to recover from unhandled rejection...')
    bot = initBot()
    setupBotEvents(bot)
    bot.start()
  }, 5000)
})

// Set timeout for QR code
const qrTimeout = setTimeout(() => {
  console.error('Timeout: QR code not received after 30 seconds')
  // Don't exit, try to reinitialize
  console.log('Debug: Attempting to recover from QR timeout...')
  bot = initBot()
  setupBotEvents(bot)
  bot.start()
}, 30000)

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('\nGracefully shutting down...')
  if (fs.existsSync(STATE_FILE)) {
    fs.unlinkSync(STATE_FILE)
  }
  process.exit(0)
})

// Start the bot with debug logging
console.log('Starting WeChat bot...')
console.log('Debug: Node.js version:', process.version)
console.log('Debug: wechat4u version:', require('wechat4u/package.json').version)

try {
  // Initialize and start bot
  bot = initBot()
  setupBotEvents(bot)
  bot.start()
  console.log('Debug: Bot start() called successfully')
  
  // Start summary scheduling
  summarizer.startScheduling(config)
  console.log('Debug: Summary scheduling started')
} catch (error) {
  console.error('Error starting bot:', error)
  // Don't exit, try to recover
  setTimeout(() => {
    console.log('Debug: Attempting to recover from startup error...')
    bot = initBot()
    setupBotEvents(bot)
    bot.start()
  }, 5000)
}
