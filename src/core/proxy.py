import aiohttp
import random
from typing import List, Dict, Optional
from src.utils.logger import logger
from src.utils.config import config
import time
import websockets

class ProxyManager:
    def __init__(self):
        self.proxies: List[Dict] = []
        self.working_proxies: List[Dict] = []
        self.used_proxies: Dict[str, str] = {}  # token -> proxy_url 映射
        self.check_interval = 300

    async def load_proxies(self, file_path: str):
        """加载代理列表"""
        try:
            with open(file_path, 'r') as f:
                proxy_lines = [line.strip() for line in f if line.strip()]
            
            logger.info(f"Loading {len(proxy_lines)} proxies...")
            
            for line in proxy_lines:
                try:
                    host, port, username, password = line.strip().split(':')
                    proxy = {
                        'host': host,
                        'port': port,
                        'username': username,
                        'password': password,
                        'url': f'http://{username}:{password}@{host}:{port}',
                        'fails': 0,
                        'last_used': 0
                    }
                    self.proxies.append(proxy)
                except Exception as e:
                    logger.error(f"Invalid proxy format: {line} - {str(e)}")
                    continue
            
            # 初始检查代理
            await self.check_proxies()
            logger.info(f"Found {len(self.working_proxies)} working proxies")
            
        except Exception as e:
            logger.error(f"Failed to load proxies: {str(e)}")
            raise

    async def check_proxies(self):
        """检查代理可用性"""
        # 限制并发检查数量
        max_concurrent = 5
        chunks = [self.proxies[i:i + max_concurrent] for i in range(0, len(self.proxies), max_concurrent)]
        
        for chunk in chunks:
            tasks = [self.check_proxy(proxy) for proxy in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for proxy, result in zip(chunk, results):
                if isinstance(result, bool) and result:
                    self.working_proxies.append(proxy)
                    logger.info(f"Proxy working: {proxy['host']}:{proxy['port']}")
                else:
                    logger.warning(f"Proxy failed: {proxy['host']}:{proxy['port']}")
            
            # 添加延迟避免请求过快
            await asyncio.sleep(2)

    async def check_proxy(self, proxy: Dict) -> bool:
        """检查单个代理"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(ssl=False, force_close=True)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
                
                # 测试Discord API
                async with session.get(
                    'https://discord.com/api/v9/gateway',
                    proxy=proxy['url'],
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        return False
                    
                # 测试WebSocket连接
                ws_url = 'wss://gateway.discord.gg/?v=9&encoding=json'
                try:
                    ws = await websockets.connect(
                        ws_url,
                        proxy=proxy['url'],
                        extra_headers=headers,
                        ssl=False
                    )
                    await ws.close()
                    return True
                except:
                    return False
                
        except Exception as e:
            logger.error(f"Proxy check failed: {proxy['host']}:{proxy['port']} - {str(e)}")
            return False

    def get_proxy(self, token: str) -> Optional[Dict]:
        """获取代理，确保每个token使用唯一的代理"""
        try:
            # 如果token已经分配了代理，继续使用该代理
            if token in self.used_proxies:
                proxy = next((p for p in self.working_proxies if p['url'] == self.used_proxies[token]), None)
                if proxy and proxy['fails'] < 3:
                    return proxy

            # 获取未使用的代理
            used_urls = set(self.used_proxies.values())
            available_proxies = [
                p for p in self.working_proxies 
                if p['url'] not in used_urls and p['fails'] < 3
            ]

            if not available_proxies:
                print("Warning: No available proxies, trying without proxy")
                return None  # 如果没有可用代理，返回None而不是抛出异常

            # 选择失败次数最少的代理
            proxy = min(available_proxies, key=lambda x: x['fails'])
            self.used_proxies[token] = proxy['url']
            return proxy

        except Exception as e:
            print(f"Warning: Proxy error: {str(e)}, trying without proxy")
            return None