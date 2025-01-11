const Wechat4u = require('wechat4u')
const fs = require('fs-extra')
const dayjs = require('dayjs')
const path = require('path')
const summarizer = require('./summarizer')

// Ensure required directories exist
fs.ensureDirSync('logs')
fs.ensureDirSync('media')
fs.ensureDirSync('summaries')

// Initialize bot
const bot = new Wechat4u()

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

// Listen for scan event (QR Code)
bot.on('scan', ({url}) => {
  console.log('\n==================================')
  console.log('Scan QR Code to login:', url)
  console.log('==================================\n')
})

// Listen for login
bot.on('login', () => {
  console.log('\n==================================')
  console.log('Successfully logged in!')
  console.log('==================================\n')
  
  // Update group list after login
  updateGroupList()
})

// Listen for logout
bot.on('logout', () => {
  console.log('\n==================================')
  console.log('Logged out!')
  console.log('==================================\n')
})

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

// Start the bot
console.log('Starting WeChat bot...')
bot.start()

// Start summary scheduling
summarizer.startScheduling(config)
