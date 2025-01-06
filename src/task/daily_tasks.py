import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict
from src.utils.logger import logger
from src.utils.config import config
from src.core.ai import AIClient

# ... 其余代码保持不变 ...

class DailyTaskManager:
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = AIClient()
        self.daily_message_count = 0
        self.last_reset_date = datetime.now().date()
        
        # 早安晚安消息模板
        self.greetings = {
            'morning': [
                'GM', 'Good Morning', 'Good morning everyone', 
                'GM fam', 'Morning all', 'GM MONAD'
            ],
            'night': [
                'GN', 'Good Night', 'Good night everyone',
                'GN fam', 'Night all', 'Sweet dreams'
            ]
        }

    async def reset_daily_count(self):
        """重置每日消息计数"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_message_count = 0
            self.last_reset_date = current_date

    async def can_send_message(self) -> bool:
        """检查是否可以发送消息"""
        await self.reset_daily_count()
        return self.daily_message_count < config.get('limits.daily_messages', 50)

    async def increment_message_count(self):
        """增加消息计数"""
        self.daily_message_count += 1

    async def send_daily_greeting(self):
        """发送每日问候"""
        try:
            # 确定是早安还是晚安
            hour = datetime.now().hour
            greeting_type = 'morning' if 5 <= hour < 12 else 'night'
            
            # 随机选择问候语
            greeting = random.choice(self.greetings[greeting_type])
            
            # 发送问候
            channel_id = config.get('discord.greeting_channel_id')
            await self.bot.send_message(channel_id, greeting)
            await self.increment_message_count()
            
            # 随机等待
            await asyncio.sleep(random.uniform(10, 40))
            
        except Exception as e:
            logger.error(f"Daily greeting error: {str(e)}")

    async def send_project_praise(self):
        """发送项目赞美"""
        try:
            # 构建AI提示
            prompt = {
                "role": "system",
                "content": """You are an enthusiastic community member of MONAD project. 
                Generate a unique, positive message about MONAD project (2-3 sentences). 
                Focus on different aspects like technology, team, community, or future potential. 
                Make it sound natural and conversational."""
            }
            
            # 获取AI响应
            response = await self.ai_client.get_response("", context={"prompt": prompt})
            
            if response:
                channel_id = config.get('discord.main_channel_id')
                await self.bot.send_message(channel_id, response)
                await self.increment_message_count()
            
        except Exception as e:
            logger.error(f"Project praise error: {str(e)}")

    def is_high_quality_message(self, message: Dict) -> bool:
        """判断是否是高质量消息"""
        content = message.get('content', '').lower()
        
        # 排除条件
        if len(content) < 10:  # 太短的消息
            return False
        
        if content.startswith(('gm', 'gn', '!')):  # 简单问候和命令
            return False
            
        # 包含项目关键词
        keywords = config.get('keywords.project', [])
        if not any(keyword in content for keyword in keywords):
            return False
            
        return True

    async def process_historical_messages(self):
        """处理历史消息"""
        try:
            channel_id = config.get('discord.main_channel_id')
            
            # 获取5小时内的消息
            five_hours_ago = datetime.utcnow() - timedelta(hours=5)
            
            async for message in self.bot.fetch_messages(channel_id, limit=100):
                # 检查消息时间
                message_time = datetime.fromisoformat(message['timestamp'])
                if message_time < five_hours_ago:
                    break
                    
                # 检查是否是高质量消息
                if self.is_high_quality_message(message):
                    # 检查是否可以发送消息
                    if not await self.can_send_message():
                        logger.info("Daily message limit reached")
                        break
                        
                    # 获取AI响应
                    response = await self.ai_client.process_message(message)
                    if response:
                        await asyncio.sleep(random.uniform(5, 15))
                        await self.bot.send_message(channel_id, response)
                        await self.increment_message_count()
                        
        except Exception as e:
            logger.error(f"Historical message processing error: {str(e)}")