const fs = require('fs-extra')
const dayjs = require('dayjs')
const path = require('path')

class MessageSummarizer {
  constructor() {
    this.summaryInterval = null
  }

  // Start daily summary scheduling
  startScheduling(config) {
    if (this.summaryInterval) {
      clearInterval(this.summaryInterval)
    }

    // Parse summary time
    const [hour, minute] = config.summaryTime.split(':').map(Number)
    
    // Calculate next summary time
    const getNextSummaryTime = () => {
      const now = dayjs()
      let next = now.hour(hour).minute(minute).second(0)
      if (next.isBefore(now)) {
        next = next.add(1, 'day')
      }
      return next
    }

    // Schedule next summary
    const scheduleNextSummary = () => {
      const now = dayjs()
      const nextTime = getNextSummaryTime()
      const msUntilNext = nextTime.diff(now)
      
      setTimeout(() => {
        this.generateDailySummaries(config.monitoredGroups)
        // Schedule next day's summary
        this.summaryInterval = setInterval(
          () => this.generateDailySummaries(config.monitoredGroups),
          24 * 60 * 60 * 1000
        )
      }, msUntilNext)
    }

    // Start scheduling
    scheduleNextSummary()
  }

  // Generate summaries for all monitored groups
  async generateDailySummaries(monitoredGroups) {
    const dateStr = dayjs().subtract(1, 'day').format('YYYY-MM-DD')
    console.log(`\nGenerating summaries for ${dateStr}...`)

    for (const groupId of monitoredGroups) {
      await this.generateGroupSummary(groupId, dateStr)
    }
  }

  // Generate summary for a specific group
  async generateGroupSummary(groupId, dateStr) {
    try {
      const logFile = path.join('logs', `group_${groupId}_${dateStr}.log`)
      
      if (!fs.existsSync(logFile)) {
        console.log(`No messages found for group ${groupId} on ${dateStr}`)
        return
      }

      const messages = await fs.readFile(logFile, 'utf8')
      const lines = messages.split('\n').filter(line => line.trim())
      
      // Analyze messages
      const stats = this.analyzeMessages(lines)
      
      // Generate summary
      const summary = this.createSummary(stats, dateStr, groupId)
      
      // Save summary
      const summaryFile = path.join('summaries', `summary_${groupId}_${dateStr}.txt`)
      await fs.writeFile(summaryFile, summary)
      
      console.log(`Generated summary for group ${groupId}`)
      
    } catch (error) {
      console.error(`Error generating summary for group ${groupId}:`, error)
    }
  }

  // Analyze messages to generate statistics
  analyzeMessages(lines) {
    const stats = {
      totalMessages: lines.length,
      users: new Map(),
      messageTypes: new Map(),
      hourlyActivity: new Array(24).fill(0),
      topMessages: []
    }

    for (const line of lines) {
      try {
        // Parse message line
        const match = line.match(/^(.+?) - (.+?): (.+)$/)
        if (!match) continue

        const [_, timestamp, user, content] = match
        const hour = dayjs(timestamp).hour()

        // Update user statistics
        stats.users.set(user, (stats.users.get(user) || 0) + 1)

        // Update message type statistics
        const type = content.startsWith('[') ? content.match(/^\[(.*?)\]/)?.[1] || 'Text' : 'Text'
        stats.messageTypes.set(type, (stats.messageTypes.get(type) || 0) + 1)

        // Update hourly activity
        stats.hourlyActivity[hour]++

        // Store message for potential highlights
        if (content.length > 10) {
          stats.topMessages.push({ user, content, timestamp })
        }

      } catch (error) {
        console.error('Error analyzing message line:', error)
      }
    }

    return stats
  }

  // Create a formatted summary
  createSummary(stats, dateStr, groupId) {
    const summary = []
    summary.push(`Daily Summary for Group ${groupId}`)
    summary.push(`Date: ${dateStr}`)
    summary.push('=' .repeat(50))
    summary.push('')

    // Overall statistics
    summary.push('📊 Overall Statistics')
    summary.push(`Total Messages: ${stats.totalMessages}`)
    summary.push('')

    // Top contributors
    summary.push('👥 Top Contributors')
    const topUsers = [...stats.users.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
    
    topUsers.forEach(([user, count], index) => {
      summary.push(`${index + 1}. ${user}: ${count} messages`)
    })
    summary.push('')

    // Message types
    summary.push('📝 Message Types')
    for (const [type, count] of stats.messageTypes) {
      summary.push(`${type}: ${count}`)
    }
    summary.push('')

    // Activity pattern
    summary.push('⏰ Activity Pattern')
    const maxActivity = Math.max(...stats.hourlyActivity)
    stats.hourlyActivity.forEach((count, hour) => {
      if (count > 0) {
        const bar = '█'.repeat(Math.ceil((count / maxActivity) * 20))
        summary.push(`${hour.toString().padStart(2, '0')}:00 ${bar} (${count})`)
      }
    })

    return summary.join('\n')
  }
}

module.exports = new MessageSummarizer()
