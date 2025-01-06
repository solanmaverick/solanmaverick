import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict
from utils.logger import logger
from utils.config import config
from core.ai import AIClient

class DailyTaskManager:
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = AIClient(bot.user_id, bot)
        self.daily_message_count = 0
        self.last_reset_date = datetime.now().date()
        self.last_greeting_time = None
        
        # 早安晚安消息模板
        self.greetings = {
            'morning': [
                'GM', 'Good Morning', 'Good morning everyone', 
                'GM fam', 'Morning all', 'GM MONAD',
                '早上好', 'GM MONAD 社区', '早安'
            ],
            'night': [
                'GN', 'Good Night', 'Good night everyone',
                'GN fam', 'Night all', 'Sweet dreams',
                '晚安', 'GN MONAD 社区', '好梦'
            ]
        }

    async def start_daily_routine(self):
        """开始每日例行任务"""
        try:
            while self.bot.running:
                await self.reset_daily_count()
                
                # 检查是否在活动时间窗口内
                current_hour = datetime.now().hour
                
                if 5 <= current_hour < 11:  # 早晨时间窗口
                    if await self.should_send_greeting('morning'):
                        await self.send_daily_greeting('morning')
                elif 21 <= current_hour <= 23:  # 晚上时间窗口
                    if await self.should_send_greeting('night'):
                        await self.send_daily_greeting('night')
                
                # 处理历史消息
                if await self.can_send_message():
                    await self.process_historical_messages()
                
                # 随机延迟
                await asyncio.sleep(random.uniform(300, 600))  # 5-10分钟
                
        except Exception as e:
            logger.error(f"Daily routine error: {str(e)}")

    async def should_send_greeting(self, greeting_type: str) -> bool:
        """检查是否应该发送问候"""
        if not self.last_greeting_time:
            return True
            
        current_time = datetime.now()
        time_diff = current_time - self.last_greeting_time
        
        # 确保同一类型的问候至少间隔4小时
        return time_diff.total_seconds() > 14400  # 4小时 = 14400秒

    def is_high_quality_message(self, message: Dict) -> bool:
        """判断是否是高质量消息"""
        if not message.get('content'):
            return False
            
        content = message['content'].lower()
        
        # 排除条件
        if len(content.split()) < 5:  # 太短的消息
            return False
            
        if content.startswith(('gm', 'gn', '!')):  # 简单问候和命令
            return False
            
        # 检查是否包含项目关键词
        keywords = config.get('keywords.project', [])
        if not any(keyword.lower() in content for keyword in keywords):
            return False
            
        # 检查消息长度和质量
        words = content.split()
        if len(words) > 50:  # 太长的消息可能是垃圾信息
            return False
            
        # 检查是否包含URL
        if 'http' in content or 'www.' in content:
            return False
            
        return True

    async def send_message_with_retry(self, channel_id: str, content: str, max_retries: int = 3):
        """带重试机制的消息发送"""
        for attempt in range(max_retries):
            try:
                await self.bot.send_message(channel_id, content)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send message after {max_retries} attempts: {str(e)}")
                    return False
                await asyncio.sleep(5 * (attempt + 1))
        return False

    async def process_historical_messages(self):
        """处理历史消息"""
        try:
            channel_id = config.get('discord.main_channel_id')
            if not channel_id:
                logger.error("Main channel ID not configured")
                return
            
            # 获取5小时内的消息
            five_hours_ago = datetime.utcnow() - timedelta(hours=5)
            processed_messages = set()  # 用于跟踪已处理的消息
            
            async for message in self.bot.fetch_messages(channel_id, limit=100):
                # 检查消息是否已处理
                if message['id'] in processed_messages:
                    continue
                
                # 检查消息时间
                message_time = datetime.fromisoformat(message['timestamp'].rstrip('Z'))
                if message_time < five_hours_ago:
                    break
                
                # 检查是否是高质量消息
                if self.is_high_quality_message(message):
                    # 检查是否可以发送消息
                    if not await self.can_send_message():
                        logger.info("Daily message limit reached")
                        break
                    
                    try:
                        # 获取AI响应
                        response = await self.ai_client.process_message(message)
                        if response:
                            # 随机延迟
                            await asyncio.sleep(random.uniform(20, 40))
                            
                            # 发送消息
                            await self.bot.send_message(channel_id, response)
                            await self.increment_message_count()
                            
                            # 记录已处理的消息
                            processed_messages.add(message['id'])
                            
                            # 添加额外延迟避免频繁发送
                            await asyncio.sleep(random.uniform(30, 60))
                            
                    except Exception as e:
                        logger.error(f"Failed to process message {message['id']}: {str(e)}")
                        continue
                    
        except Exception as e:
            logger.error(f"Historical message processing error: {str(e)}") 

    async def reset_daily_count(self):
        """Reset daily message count if it's a new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_message_count = 0
            self.last_reset_date = current_date
            logger.info(f"Reset daily message count for bot {self.bot.user_id}")

    async def send_daily_greeting(self, greeting_type: str):
        """Send a daily greeting message"""
        channel_id = config.get('discord.greeting_channel_id')
        if not channel_id:
            logger.error("No greeting channel configured")
            return
            
        greetings_list = self.greetings.get(greeting_type, [])
        if not greetings_list:
            logger.error(f"No greetings found for type: {greeting_type}")
            return
            
        # Choose random greeting
        greeting_msg = random.choice(greetings_list)
        
        # Send with retry mechanism
        success = await self.send_message_with_retry(channel_id, greeting_msg)
        if success:
            self.last_greeting_time = datetime.now()
            await self.increment_message_count()
            logger.info(f"Sent {greeting_type} greeting: {greeting_msg}")
        else:
            logger.error(f"Failed to send {greeting_type} greeting")

    async def can_send_message(self) -> bool:
        """Check if the bot can send more messages today"""
        await self.reset_daily_count()  # Ensure count is reset if it's a new day
        daily_limit = config.get('limits.daily_messages', 30)
        can_send = self.daily_message_count < daily_limit
        if not can_send:
            logger.info(f"Daily message limit ({daily_limit}) reached for bot {self.bot.user_id}")
        return can_send

    async def increment_message_count(self):
        """Increment the daily message count"""
        self.daily_message_count += 1
        logger.debug(f"Incremented message count to {self.daily_message_count} for bot {self.bot.user_id}")
     