from typing import Dict, Any
from src.utils.logger import logger
from src.utils.config import config
from src.core.ai import AIClient
import asyncio
import random

class MessageHandler:
    def __init__(self):
        self.ai_client = None  # Will be initialized per bot in handle method
        self.last_response_time = {}  # 记录每个机器人最后回复时间
        self.daily_message_counts = {}  # 记录每个机器人的每日消息计数

    async def handle(self, bot, message_data: Dict[str, Any]):
        """处理消息"""
        try:
            # 忽略自己的消息
            if message_data['author']['id'] == bot.user_data['id']:
                return

            # 检查是否是目标频道
            if message_data['channel_id'] != config.get('discord.channel_id'):
                return

            # 检查每日消息限制
            bot_id = bot.user_data['id']
            if self.daily_message_counts.get(bot_id, 0) >= config.get('limits.daily_messages', 50):
                logger.info(f"Bot {bot.user_data['username']} reached daily message limit")
                return

            # 构建消息上下文
            context = {
                'channel_id': message_data['channel_id'],
                'author': message_data['author']['username'],
                'bot_id': bot.user_data['id'],
                'content': message_data.get('content', '')
            }

            # 检查是否需要响应
            if await self.should_respond(context):
                # 获取AI响应
                if not hasattr(bot, '_ai_client'):
                    bot._ai_client = AIClient(bot.user_data['id'], bot)
                response = await bot._ai_client.process_message(context)
                
                if response:
                    # 添加随机延迟
                    await asyncio.sleep(random.uniform(20, 40))  # Changed from 5,20
                    
                    # 发送消息
                    await bot.send_message(
                        message_data['channel_id'],
                        response
                    )
                    
                    # 更新计数
                    self.daily_message_counts[bot_id] = self.daily_message_counts.get(bot_id, 0) + 1

        except Exception as e:
            logger.error(f"Message handling error: {str(e)}")

    async def should_respond(self, context: Dict[str, Any]) -> bool:
        """判断是否需要响应消息"""
        content = context['content'].lower()
        
        # 检查是否被@
        if f"<@{context['bot_id']}>" in content:
            return True
            
        # 检查项目关键词
        project_keywords = config.get('keywords.project', [])
        if any(keyword.lower() in content for keyword in project_keywords):
            return True
            
        # 忽略简单问候
        ignore_words = config.get('keywords.ignore', ['gm', 'gn', 'good morning', 'good night'])
        if any(word.lower() in content for word in ignore_words):
            return False
            
        # 检查消息质量
        if len(content.split()) < 5:  # 太短的消息
            return False
            
        return False  # 默认不响应

    async def reset_daily_counts(self):
        """重置每日消息计数"""
        self.daily_message_counts.clear()
