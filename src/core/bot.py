import base64
import uuid
import random
import json
import asyncio
import aiohttp
import websockets.client as websockets
from datetime import datetime
from typing import Optional, Dict, Any
import time

from utils.logger import logger
from utils.config import config
from utils.helpers import RateLimiter, random_delay
from handlers.message import MessageHandler
from handlers.verification import VerificationHandler
from ..tasks.daily_tasks import DailyTaskManager
from handlers.captcha import CaptchaSolver

class DiscordBot:
    def __init__(self, token: str, proxy: Dict[str, str]):
        self.token = token
        self.proxy = proxy
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.user_data: Optional[Dict[str, Any]] = None
        self.heartbeat_interval: Optional[int] = None
        self.last_sequence: Optional[int] = None
        
        # 处理器初始化
        self.message_handler = MessageHandler()
        self.verification_handler = VerificationHandler()
        self.daily_tasks = DailyTaskManager(self)
        self.captcha_solver = CaptchaSolver()  # 添加验证码解决器
        
        # 速率限制
        self.rate_limiter = RateLimiter(calls=50, period=60)
        
        # 状态标志
        self.is_connected = False
        self.is_ready = False
        self.running = True

    async def initialize(self):
        """初始化机器人"""
        try:
            # 创建HTTP会话
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "Authorization": self.token,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            # 验证令牌
            if not await self._verify_token():
                raise Exception("Invalid token")
            
            # 获取用户信息
            await self._fetch_user_data()
            logger.info(f"Bot initialized: {self.user_data.get('username', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Bot initialization failed: {str(e)}")
            raise

    async def _fetch_user_data(self):
        """获取用户信息"""
        async with self.session.get(
            "https://discord.com/api/v9/users/@me",
            proxy=self.proxy['url']
        ) as resp:
            if resp.status == 200:
                self.user_data = await resp.json()
            else:
                raise Exception(f"Failed to fetch user data: {resp.status}")

    async def connect(self):
        """建立WebSocket连接"""
        try:
            # 获取网关URL
            gateway_url = await self._get_gateway()
            
            # 配置WebSocket连接
            websocket_options = {
                'proxy': self.proxy['url'],
                'extra_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Origin': 'https://discord.com',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'Upgrade',
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache',
                },
                'max_size': 1024 * 1024 * 4,  # 4MB
                'compression': None,
                'ssl': False,
                'close_timeout': 30,
            }
            
            # 建立WebSocket连接
            self.ws = await websockets.connect(gateway_url, **websocket_options)
            
            # 接收Hello消息
            hello_msg = await self.ws.recv()
            hello_data = json.loads(hello_msg)
            
            if hello_data['op'] == 10:
                self.heartbeat_interval = hello_data['d']['heartbeat_interval']
                logger.info(f"Received heartbeat interval: {self.heartbeat_interval}ms")
                
                # 发送身份验证
                await self._identify()
                
                # 等待Ready事件
                ready = False
                timeout = 30  # 30秒超时
                start_time = time.time()
                
                while not ready and self.running:
                    if time.time() - start_time > timeout:
                        raise Exception("Timeout waiting for READY event")
                        
                    msg = await self.ws.recv()
                    data = json.loads(msg)
                    
                    if data['t'] == 'READY':
                        ready = True
                        logger.info(f"Bot {self.user_data['username']} received READY event")
                    elif data.get('op') == 9:  # Invalid session
                        raise Exception("Invalid session")
                
                # 启动心跳和消息处理
                self.heartbeat_task = asyncio.create_task(self._heartbeat())
                self.message_task = asyncio.create_task(self._message_loop())
                
                self.is_connected = True
                logger.info(f"Bot {self.user_data['username']} connected successfully")
                
            else:
                raise Exception(f"Invalid gateway response: {hello_data}")
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise

    async def start_daily_routine(self):
        """开始每日例行任务"""
        try:
            # 随机延迟启动
            await asyncio.sleep(random.uniform(10, 30))
            
            # 发送每日问候
            await self.daily_tasks.send_daily_greeting()
            
            # 随机延迟
            await asyncio.sleep(random.uniform(10, 40))
            
            # 发送项目赞美
            await self.daily_tasks.send_project_praise()
            
            # 随机延迟
            await asyncio.sleep(random.uniform(10, 30))
            
            # 处理历史消息
            await self.daily_tasks.process_historical_messages()
            
        except Exception as e:
            logger.error(f"Daily routine error: {str(e)}")

    async def _get_gateway(self) -> str:
        """获取WebSocket网关URL"""
        async with self.session.get(
            "https://discord.com/api/v9/gateway"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return f"{data['url']}/?v=9&encoding=json"
            raise Exception(f"Failed to get gateway: {resp.status}")

    async def _identify(self):
        """发送身份验证信息"""
        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "capabilities": 16381,
                "properties": {
                    "os": "Windows",
                    "browser": "Chrome",
                    "device": "",
                    "system_locale": "zh-CN",
                    "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "browser_version": "122.0.0.0",
                    "os_version": "10",
                    "referrer": "",
                    "referring_domain": "",
                    "referrer_current": "",
                    "referring_domain_current": "",
                    "release_channel": "stable",
                    "client_build_number": 246997,
                    "client_event_source": None
                },
                "presence": {
                    "status": "online",
                    "since": 0,
                    "activities": [],
                    "afk": False
                },
                "compress": False,
                "client_state": {
                    "guild_versions": {},
                    "highest_last_message_id": "0",
                    "read_state_version": 0,
                    "user_guild_settings_version": -1,
                    "user_settings_version": -1,
                    "private_channels_version": "0",
                    "api_code_version": 0
                }
            }
        }
        await self.ws.send(json.dumps(payload))

    async def _heartbeat(self):
        """心跳维持"""
        while self.running:
            try:
                if self.heartbeat_interval:
                    await asyncio.sleep(self.heartbeat_interval / 1000)
                    await self.ws.send(json.dumps({
                        "op": 1,
                        "d": self.last_sequence
                    }))
            except Exception as e:
                logger.error(f"Heartbeat failed: {str(e)}")
                await self.reconnect()

    async def _message_loop(self):
        """消息处理循环"""
        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                    data = json.loads(message)
                    
                    # 更新最后收到的序列号
                    if data.get('s'):
                        self.last_sequence = data['s']
                    
                    if data['op'] == 11:  # Heartbeat ACK
                        continue
                        
                    elif data['op'] == 7:  # Reconnect
                        logger.info("Received reconnect request")
                        await self.reconnect()
                        break
                        
                    elif data['op'] == 9:  # Invalid Session
                        logger.warning("Received invalid session")
                        await self.reconnect()
                        break
                        
                    elif data['t'] == 'MESSAGE_CREATE':
                        await self.message_handler.handle(self, data['d'])
                        
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    await self.reconnect()
                    break
                except Exception as e:
                    logger.error(f"Message loop error: {str(e)}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"Fatal error in message loop: {str(e)}")
            await self.reconnect()

    async def _handle_event(self, data: Dict):
        """处理Discord事件"""
        op = data.get('op')
        t = data.get('t')
        
        if op == 10:  # Hello
            self.heartbeat_interval = data['d']['heartbeat_interval']
        
        elif op == 0:  # Dispatch
            if t == 'READY':
                self.is_ready = True
                logger.info(f"Bot {self.user_data['username']} is ready")
            
            elif t == 'MESSAGE_CREATE':
                # 检查每日消息限制
                if await self.daily_tasks.can_send_message():
                    await self.message_handler.handle(self, data['d'])
            
            elif t == 'GUILD_MEMBER_ADD':
                if data['d']['user']['id'] == self.user_data['id']:
                    await self.verification_handler.handle(self, data['d'])

    async def send_message(self, channel_id: str, content: str):
        """发送消息"""
        await self.rate_limiter.acquire()
        
        try:
            async with self.session.post(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                json={"content": content},
                proxy=self.proxy['url']
            ) as resp:
                if resp.status == 200:
                    await self.daily_tasks.increment_message_count()
                    return await resp.json()
                else:
                    logger.error(f"Failed to send message: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            return None

    async def fetch_messages(self, channel_id: str, limit: int = 100):
        """获取频道消息"""
        try:
            async with self.session.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                params={"limit": limit},
                proxy=self.proxy['url']
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except Exception as e:
            logger.error(f"Fetch messages error: {str(e)}")
            return []

    async def join_server(self, invite_code: str):
        """加入服务器"""
        try:
            logger.info(f"Bot {self.user_data['username']} attempting to join server")
            
            # 获取邀请信息
            async with self.session.get(
                f"https://discord.com/api/v9/invites/{invite_code}",
                headers=self._get_headers(),
                proxy=self.proxy['url']
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to get invite info: {resp.status}")
                    return False
                invite_data = await resp.json()

            # 解决hCaptcha
            try:
                captcha_token = await self.captcha_solver.solve_hcaptcha(
                    "a9b5fb07-92ff-493f-86fe-352a2803b3df",
                    f"https://discord.com/invite/{invite_code}"
                )
            except Exception as e:
                logger.error(f"Failed to solve captcha: {str(e)}")
                return False

            # 加入服务器
            join_payload = {
                "captcha_key": captcha_token,
                "consent": True
            }

            async with self.session.post(
                f"https://discord.com/api/v9/invites/{invite_code}",
                headers=self._get_headers(),
                json=join_payload,
                proxy=self.proxy['url']
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to join server: {resp.status}")
                    return False

            logger.info(f"Bot {self.user_data['username']} successfully joined server")
            return True

        except Exception as e:
            logger.error(f"Join server error: {str(e)}")
            return False

    def _get_headers(self):
        """获取请求头"""
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMi4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIyLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjIyMDgzNiwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0="
        }

    async def solve_hcaptcha(self, sitekey: str, url: str) -> str:
        """解决hCaptcha验证"""
        try:
            # 使用配置的验证码解决服务
            solver = self.captcha_solver  # 这需要在初始化时创建
            token = await solver.solve_hcaptcha(sitekey, url)
            return token
        except Exception as e:
            logger.error(f"hCaptcha solving error: {str(e)}")
            raise

    async def reconnect(self):
        """重新连接"""
        self.is_connected = False
        self.is_ready = False
        
        try:
            if self.ws:
                await self.ws.close()
            if self.session:
                await self.session.close()
            
            await random_delay(5, 10)
            await self.initialize()
            await self.connect()
            
        except Exception as e:
            logger.error(f"Reconnection failed: {str(e)}")
            raise

    async def close(self):
        """关闭连接"""
        self.running = False
        try:
            # 取消所有任务
            if hasattr(self, 'heartbeat_task'):
                self.heartbeat_task.cancel()
            if hasattr(self, 'message_task'):
                self.message_task.cancel()
            
            # 关闭WebSocket连接
            if self.ws:
                await self.ws.close()
            
            # 关闭HTTP会话
            if self.session:
                await self.session.close()
            
            # 关闭验证码解决器
            if hasattr(self, 'captcha_solver'):
                await self.captcha_solver.close()
            
            # 关闭AI客户端
            if hasattr(self, 'daily_tasks') and hasattr(self.daily_tasks, 'ai_client'):
                await self.daily_tasks.ai_client.close()
            
            self.is_connected = False
            self.is_ready = False
            logger.info(f"Bot {self.user_data['username']} closed successfully")
            
        except Exception as e:
            logger.error(f"Close connection error: {str(e)}")

    async def _verify_token(self) -> bool:
        """验证令牌是否有效"""
        try:
            async with self.session.get(
                "https://discord.com/api/v9/users/@me",
                headers={"Authorization": self.token},
                proxy=self.proxy['url']
            ) as resp:
                if resp.status == 200:
                    user_data = await resp.json()
                    logger.info(f"Token verified for user: {user_data.get('username', 'Unknown')}")
                    return True
                else:
                    logger.error(f"Invalid token: Status {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return False

    async def check_token_status(self):
        """检查账号状态"""
        try:
            if not self.session:
                connector = aiohttp.TCPConnector(ssl=False)
                self.session = aiohttp.ClientSession(connector=connector)

            headers = {
                "Authorization": self.token,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "DNT": "1",
                "Origin": "https://discord.com",
                "Referer": "https://discord.com",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin"
            }

            # 尝试获取用户信息
            async with self.session.get(
                "https://discord.com/api/v9/users/@me",
                headers=headers,
                proxy=self.proxy['url'] if self.proxy else None  # 先测试不使用代理
            ) as resp:
                if resp.status == 200:
                    user_data = await resp.json()
                    print(f"\n✓ Token VALID - Username: {user_data.get('username')}#{user_data.get('discriminator')}")
                    print(f"  ID: {user_data.get('id')}")
                    print(f"  Email verified: {user_data.get('verified')}")
                    print(f"  Phone: {'Yes' if user_data.get('phone') else 'No'}")
                    return True, user_data
                else:
                    error = await resp.text()
                    print(f"\n✗ Token check failed - Status: {resp.status}")
                    print(f"  Error: {error}")
                    return False, None

        except Exception as e:
            print(f"\n! Error checking token: {str(e)}")
            return False, None