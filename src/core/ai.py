import json
import random
import asyncio
import aiohttp
from typing import Dict, Optional, List
from src.utils.logger import logger
from src.utils.config import config

class AIClient:
    def __init__(self, bot_id: str, bot):
        self.bot_id = bot_id
        self.bot = bot  # Store bot reference for context fetching
        self.api_key = config.get('ai.api_key')
        self.api_endpoint = "https://api.openai.com/v1/chat/completions"
        self.session: Optional[aiohttp.ClientSession] = None
        self.conversation_history: Dict[str, List[Dict]] = {}  # Track per-bot conversations
        
        # 忽略词列表
        self.ignore_words = {'gm', 'gn', 'good morning', 'good night'}
        
        # 项目相关关键词
        self.project_keywords = {'monad', 'project', 'team'}

    async def initialize(self):
        """初始化AI客户端"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )

    async def should_respond(self, message: str) -> bool:
        """判断是否需要响应消息"""
        message_lower = message.lower()
        
        # 忽略简单问候
        if any(word in message_lower for word in self.ignore_words):
            return False
            
        # 检查是否包含项目关键词
        if any(keyword in message_lower for keyword in self.project_keywords):
            return True
            
        return False

    async def get_response(self, message: str, context: Dict = None) -> Optional[str]:
        """获取AI响应"""
        try:
            if not self.session:
                await self.initialize()

            # 构建消息内容
            messages = []
            
            # 添加系统提示
            messages.append({
                "role": "system",
                "content": "You are a friendly community member who is enthusiastic about the MONAD project. Always be supportive and positive about the project and team."
            })

            # 添加上下文（如果有）
            if context:
                messages.append({
                    "role": "system",
                    "content": f"Context: {json.dumps(context)}"
                })

            # 添加用户消息
            messages.append({
                "role": "user",
                "content": message
            })

            # 发送请求
            async with self.session.post(
                self.api_endpoint,
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 150
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    response_content = data['choices'][0]['message']['content']
                    
                    # 保存对话历史
                    if context and 'channel_info' in context:
                        channel_id = context['channel_info']
                        if channel_id not in self.conversation_history:
                            self.conversation_history[channel_id] = []
                        self.conversation_history[channel_id].append({
                            'role': 'assistant',
                            'content': response_content,
                            'bot_id': self.bot_id  # Add bot_id to track message source
                        })
                        # 保持历史记录在合理范围内
                        if len(self.conversation_history[channel_id]) > 10:
                            self.conversation_history[channel_id] = self.conversation_history[channel_id][-10:]
                    
                    return response_content
                else:
                    logger.error(f"AI API error: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"AI response error: {str(e)}")
            return None

    async def process_message(self, message: Dict) -> Optional[str]:
        """处理消息并决定是否回复"""
        try:
            content = message.get('content', '')
            
            # 检查是否被@
            if f"<@{self.bot_id}>" in content:
                # 被@时直接回复
                return await self.get_response(content)
            
            # 检查是否需要响应
            if await self.should_respond(content):
                # 添加随机延迟
                await asyncio.sleep(random.uniform(10, 30))
                
                # 构建上下文
                context = {
                    'previous_messages': await self._get_context_messages(message),
                    'user_info': message.get('author', {}),
                    'channel_info': message.get('channel_id'),
                    'timestamp': message.get('timestamp')
                }
                
                return await self.get_response(content, context)
            
            return None

        except Exception as e:
            logger.error(f"Message processing error: {str(e)}")
            return None

    async def _get_context_messages(self, current_message: Dict) -> List[Dict]:
        """获取消息上下文"""
        try:
            channel_id = current_message.get('channel_id')
            message_id = current_message.get('id')
            
            # 获取当前消息之前的几条消息
            messages = []
            async for msg in self.bot.fetch_messages(channel_id, limit=5):
                if msg['id'] != message_id:
                    messages.append({
                        'content': msg['content'],
                        'author': msg['author']['username'],
                        'timestamp': msg['timestamp']
                    })
            
            return messages
        except Exception as e:
            logger.error(f"Error getting context messages: {str(e)}")
            return []

    async def close(self):
        """关闭AI客户端"""
        if self.session:
            await self.session.close()
            self.session = None
