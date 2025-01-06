import asyncio
from typing import Dict, Any, Optional
from utils.logger import logger
from utils.config import config
from handlers.captcha import CaptchaSolver
import random

# ... 其余代码保持不变 ...

class VerificationHandler:
    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self.verification_types = {
            'REACTION': self._handle_reaction_verification,
            'BUTTON': self._handle_button_verification,
            'CAPTCHA': self._handle_captcha_verification,
            'MESSAGE': self._handle_message_verification
        }

    async def handle(self, bot, guild_data: Dict[str, Any]):
        """处理服务器验证"""
        try:
            logger.info(f"Bot {bot.user_data['username']} starting verification process...")
            
            # 等待验证频道出现
            channel_id = config.get('discord.verification_channel_id')
            await asyncio.sleep(5)  # 等待加入服务器完成
            
            # 直接点击验证按钮
            async with bot.session.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                params={"limit": 50},
                proxy=bot.proxy['url']
            ) as resp:
                if resp.status == 200:
                    messages = await resp.json()
                    for message in messages:
                        if message.get('components'):
                            for component in message['components']:
                                if component.get('type') == 1:  # Action Row
                                    for button in component.get('components', []):
                                        if button.get('type') == 2:  # Button
                                            # 点击验证按钮
                                            await self._click_button(bot, message['id'], button['custom_id'], channel_id)
                                            logger.info(f"Bot {bot.user_data['username']} clicked verification button")
                                            return True
            
            logger.warning(f"No verification button found for bot {bot.user_data['username']}")
            return False
            
        except Exception as e:
            logger.error(f"Verification handling error: {str(e)}")
            return False

    async def _click_button(self, bot, message_id: str, custom_id: str, channel_id: str):
        """点击按钮"""
        try:
            payload = {
                "type": 3,
                "guild_id": config.get('discord.guild_id'),
                "channel_id": channel_id,
                "message_id": message_id,
                "application_id": "1325497910355300362",  # 这里需要使用正确的application_id
                "session_id": "".join(random.choices("0123456789abcdef", k=32)),
                "data": {
                    "component_type": 2,
                    "custom_id": custom_id
                }
            }
            
            headers = {
                "Authorization": bot.token,
                "Content-Type": "application/json",
                "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6InpoLUNOIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMi4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIyLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjI0Njk5NywiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0="
            }
            
            async with bot.session.post(
                "https://discord.com/api/v9/interactions",
                json=payload,
                headers=headers,
                proxy=bot.proxy['url']
            ) as resp:
                if resp.status in (200, 204):
                    logger.info(f"Successfully clicked verification button")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Failed to click button: {error}")
                    return False
                
        except Exception as e:
            logger.error(f"Button click error: {str(e)}")
            return False

    async def _wait_for_verification_message(self, bot) -> Optional[Dict]:
        """等待验证消息"""
        verification_channel = config.get('discord.verification_channel_id')
        retry_count = 0
        max_retries = 5

        while retry_count < max_retries:
            try:
                messages = await bot.fetch_messages(verification_channel, limit=50)
                
                for message in messages:
                    if self._is_verification_message(message):
                        return message
                        
                await asyncio.sleep(2)
                retry_count += 1
                
            except Exception as e:
                logger.error(f"Error waiting for verification message: {str(e)}")
                retry_count += 1
                await asyncio.sleep(2)

        return None

    def _identify_verification_type(self, message: Dict) -> Optional[str]:
        """识别验证类型"""
        content = message.get('content', '').lower()
        components = message.get('components', [])
        
        if message.get('attachments') and any('captcha' in att.get('filename', '').lower() for att in message['attachments']):
            return 'CAPTCHA'
        elif components and any('button' in str(comp).lower() for comp in components):
            return 'BUTTON'
        elif '反应' in content or 'react' in content:
            return 'REACTION'
        elif '发送' in content or 'type' in content:
            return 'MESSAGE'
        return None

    async def _handle_reaction_verification(self, bot, message: Dict) -> bool:
        """处理表情反应验证"""
        try:
            # 找到需要添加的表情
            emoji = self._find_verification_emoji(message)
            if not emoji:
                return False

            # 添加表情反应
            await bot.session.put(
                f"https://discord.com/api/v9/channels/{message['channel_id']}/messages/{message['id']}/reactions/{emoji}/@me",
                proxy=bot.proxy['url']
            )
            return True

        except Exception as e:
            logger.error(f"Reaction verification failed: {str(e)}")
            return False

    async def _handle_button_verification(self, bot, message: Dict) -> bool:
        """处理按钮验证"""
        try:
            # 找到验证按钮
            components = message.get('components', [])
            button_data = self._find_verification_button(components)
            if not button_data:
                return False

            # 点击按钮
            await bot.session.post(
                f"https://discord.com/api/v9/interactions",
                json={
                    "type": 3,
                    "guild_id": message.get('guild_id'),
                    "channel_id": message['channel_id'],
                    "message_id": message['id'],
                    "data": button_data
                },
                proxy=bot.proxy['url']
            )
            return True

        except Exception as e:
            logger.error(f"Button verification failed: {str(e)}")
            return False

    async def _handle_captcha_verification(self, bot, message: Dict) -> bool:
        """处理验证码验证"""
        try:
            # 获取验证码图片
            captcha_url = self._get_captcha_url(message)
            if not captcha_url:
                return False

            # 解决验证码
            solution = await self.captcha_solver.solve(captcha_url)
            if not solution:
                return False

            # 提交验证码
            return await self._submit_captcha_solution(bot, message, solution)

        except Exception as e:
            logger.error(f"Captcha verification failed: {str(e)}")
            return False

    async def _handle_message_verification(self, bot, message: Dict) -> bool:
        """处理消息验证"""
        try:
            # 分析需要发送的消息
            required_message = self._analyze_required_message(message)
            if not required_message:
                return False

            # 发送验证消息
            await bot.send_message(
                message['channel_id'],
                required_message
            )
            return True

        except Exception as e:
            logger.error(f"Message verification failed: {str(e)}")
            return False

    def _is_verification_message(self, message: Dict) -> bool:
        """判断是否是验证消息"""
        content = message.get('content', '').lower()
        keywords = ['verify', 'verification', '验证', '认证']
        
        # 检查消息内容
        if any(keyword in content for keyword in keywords):
            return True
        
        # 检查是否包含验证组件
        if message.get('components'):
            return True
        
        # 检查是否包含验证码图片
        if message.get('attachments'):
            return any('captcha' in att.get('filename', '').lower() 
                      for att in message['attachments'])
        
        return False

    def _find_verification_emoji(self, message: Dict) -> Optional[str]:
        """查找验证用的表情"""
        # 实现表情查找逻辑
        common_verification_emojis = ['✅', '☑️', '✔️']
        for emoji in common_verification_emojis:
            if emoji in message.get('content', ''):
                return emoji
        return None

    def _find_verification_button(self, components: list) -> Optional[Dict]:
        """查找验证按钮"""
        for component in components:
            if component.get('type') == 2:  # Button type
                if any(keyword in component.get('label', '').lower() 
                      for keyword in ['verify', 'verification', '验证']):
                    return {
                        "component_type": 2,
                        "custom_id": component.get('custom_id')
                    }
        return None

    def _get_captcha_url(self, message: Dict) -> Optional[str]:
        """获取验证码图片URL"""
        attachments = message.get('attachments', [])
        for attachment in attachments:
            if 'captcha' in attachment.get('filename', '').lower():
                return attachment.get('url')
        return None

    def _analyze_required_message(self, message: Dict) -> Optional[str]:
        """分析需要发送的验证消息"""
        content = message.get('content', '').lower()
        if 'type' in content:
            # 提取引号中的内容
            import re
            match = re.search(r'"([^"]*)"', content)
            if match:
                return match.group(1)
        return None