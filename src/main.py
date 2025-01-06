import asyncio
import signal
import sys
from typing import List, Dict
from pathlib import Path
from datetime import datetime, time
import random
import aiohttp

from core.bot import DiscordBot
from core.proxy import ProxyManager
from utils.logger import logger
from utils.config import config
from utils.helpers import chunk_list

class BotManager:
    def __init__(self):
        self.bots: List[DiscordBot] = []
        self.proxy_manager = ProxyManager()
        self.running = True
        self.setup_signal_handlers()
        
        # 每日任务时间窗口
        self.morning_window = (time(5, 0), time(11, 0))  # 5:00 - 11:00
        self.night_window = (time(21, 0), time(23, 59))  # 21:00 - 23:59

    def setup_signal_handlers(self):
        """设置信号处理"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info("Shutdown signal received, cleaning up...")
        self.running = False
        asyncio.create_task(self.shutdown())

    async def initialize(self):
        """初始化管理器"""
        try:
            # 加载配置
            config.load_config()

            # 加载代理
            await self.proxy_manager.load_proxies('data/proxies.txt')
            logger.info(f"Loaded {len(self.proxy_manager.proxies)} proxies")

            # 加载token
            tokens = await self._load_tokens()
            logger.info(f"Loaded {len(tokens)} tokens")

            # 检查所有账号状态
            logger.info("Starting token status check...")
            valid_tokens = []
            
            for i, token in enumerate(tokens, 1):
                try:
                    # 为每个token分配唯一的代理
                    proxy = self.proxy_manager.get_proxy(token.strip())
                    bot = DiscordBot(token.strip(), proxy)
                    
                    # 创建HTTP会话
                    connector = aiohttp.TCPConnector(ssl=False)
                    bot.session = aiohttp.ClientSession(connector=connector)
                    
                    # 检查账号状态
                    is_valid, user_data = await bot.check_token_status()
                    
                    if is_valid:
                        valid_tokens.append(token)
                        logger.info(f"Token {i}/30 - VALID - Username: {user_data.get('username')} - ID: {user_data.get('id')}")
                    else:
                        logger.error(f"Token {i}/30 - INVALID")
                    
                    # 关闭会话
                    await bot.session.close()
                    await asyncio.sleep(1)  # 添加延迟避免请求过快
                    
                except Exception as e:
                    logger.error(f"Token {i}/30 - ERROR: {str(e)}")
                    continue

            logger.info(f"Token check completed. Valid tokens: {len(valid_tokens)}/{len(tokens)}")

            # 只使用有效的token创建机器人
            for token in valid_tokens:
                try:
                    proxy = self.proxy_manager.get_proxy(token.strip())
                    bot = DiscordBot(token.strip(), proxy)
                    self.bots.append(bot)
                except Exception as e:
                    logger.error(f"Failed to create bot: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            raise

    async def _load_tokens(self) -> List[str]:
        """加载Discord令牌"""
        token_path = Path('data/tokens.txt')
        if not token_path.exists():
            raise FileNotFoundError("Tokens file not found")

        with open(token_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]

    def is_within_time_window(self) -> bool:
        """检查当前时间是否在活动时间窗口内"""
        current_time = datetime.now().time()
        
        # 处理跨日的情况
        if self.night_window[0] <= current_time or current_time <= self.night_window[1]:
            return True
        
        if self.morning_window[0] <= current_time <= self.morning_window[1]:
            return True
        
        return False

    async def start_bots(self):
        """启动所有机器人"""
        try:
            if not self.is_within_time_window():
                logger.info("Outside of active time window, waiting...")
                return

            # 随机打乱机器人列表
            random.shuffle(self.bots)
            
            # 分批启动机器人
            chunks = chunk_list(self.bots, config.get('operation.max_concurrent_bots', 5))
            
            for chunk in chunks:
                # 为每个批次创建随机延迟
                delays = [random.uniform(1, 5) for _ in range(len(chunk))]
                
                # 创建启动任务
                tasks = [
                    self.start_single_bot(bot, delay) 
                    for bot, delay in zip(chunk, delays)
                ]
                
                # 并发启动这一批机器人
                await asyncio.gather(*tasks)
                
                # 批次间延迟
                await asyncio.sleep(config.get('operation.delay_between_chunks', 5))

        except Exception as e:
            logger.error(f"Bot startup error: {str(e)}")
            await self.shutdown()

    async def start_single_bot(self, bot: DiscordBot, initial_delay: float = 0):
        """启动单个机器人"""
        try:
            await asyncio.sleep(initial_delay)
            
            # 初始化机器人
            try:
                await bot.initialize()
                logger.info(f"Bot {bot.user_data['username']} initialized")
            except Exception as e:
                logger.error(f"Bot initialization failed for token ending in ...{bot.token[-8:]}: {str(e)}")
                return

            # 连接到Discord
            try:
                await bot.connect()
                logger.info(f"Bot {bot.user_data['username']} connected")
            except Exception as e:
                logger.error(f"Bot connection failed for {bot.user_data.get('username', 'Unknown')}: {str(e)}")
                return

            # 加入服务器
            invite_code = config.get('discord.invite_code')
            if invite_code:
                join_success = False
                max_retries = config.get('discord.join_retry.max_attempts', 3)
                
                for attempt in range(max_retries):
                    try:
                        success = await bot.join_server(invite_code)
                        if success:
                            join_success = True
                            logger.info(f"Bot {bot.user_data['username']} successfully joined server")
                            break
                        else:
                            if attempt < max_retries - 1:
                                retry_delay = config.get('discord.join_retry.delay_between_attempts', 10) * (attempt + 1)
                                logger.warning(f"Join server attempt {attempt + 1} failed for {bot.user_data['username']}, retrying in {retry_delay}s...")
                                await asyncio.sleep(retry_delay)
                            else:
                                logger.error(f"Bot {bot.user_data['username']} failed to join server after {max_retries} attempts")
                    except Exception as e:
                        logger.error(f"Join server attempt {attempt + 1} error for {bot.user_data['username']}: {str(e)}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(10 * (attempt + 1))
                
                if not join_success:
                    # 如果加入失败，标记代理为失败
                    bot.proxy['fails'] += 1
                    return

            # 等待更长时间确保加入成功
            await asyncio.sleep(15)
            
            # 执行每日例行任务
            await bot.start_daily_routine()
            
            logger.info(f"Bot {bot.user_data['username']} started successfully")

        except Exception as e:
            logger.error(f"Single bot startup error: {str(e)}")

    async def monitor_bots(self):
        """监控机器人状态"""
        while self.running:
            try:
                active_bots = len([bot for bot in self.bots if bot.is_connected])
                logger.info(f"Active bots: {active_bots}/{len(self.bots)}")
                
                for bot in self.bots:
                    if not bot.is_connected and self.running:
                        asyncio.create_task(self.reconnect_bot(bot))
                    
                    if hasattr(bot, 'daily_tasks'):
                        count = bot.daily_tasks.daily_message_count
                        logger.info(f"Bot {bot.user_data['username']} daily messages: {count}/50")
                
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Monitor error: {str(e)}")

    async def reconnect_bot(self, bot: DiscordBot):
        """重新连接机器人"""
        try:
            # 获取新代理
            new_proxy = self.proxy_manager.get_proxy()
            bot.proxy = new_proxy
            
            # 重试连接
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await bot.reconnect()
                    logger.info(f"Bot {bot.user_data['username']} reconnected successfully")
                    return
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to reconnect bot after {max_retries} attempts")
                        raise
                    logger.warning(f"Reconnection attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(5 * (attempt + 1))
                
        except Exception as e:
            logger.error(f"Reconnection error: {str(e)}")
            bot.proxy['fails'] += 1

    async def shutdown(self):
        """关闭所有机器人"""
        logger.info("Shutting down all bots...")
        shutdown_tasks = []
        
        for bot in self.bots:
            if bot.is_connected:
                shutdown_tasks.append(bot.close())
        
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.bots.clear()
        logger.info("All bots shut down successfully")

    async def run(self):
        """运行主循环"""
        try:
            await self.initialize()
            
            while self.running:
                if self.is_within_time_window():
                    await self.start_bots()
                    await self.monitor_bots()
                else:
                    logger.info("Outside of active time window, waiting...")
                    await asyncio.sleep(300)
                    
        except Exception as e:
            logger.error(f"Main loop error: {str(e)}")
        finally:
            await self.shutdown()

    async def check_tokens(self, tokens: List[str]):
        """检查所有token的状态"""
        print("\n=== Starting Token Status Check ===")
        print(f"Total tokens to check: {len(tokens)}")
        
        valid_tokens = []
        results = {
            'valid': 0,
            'invalid': 0,
            'locked': 0,
            'banned': 0,
            'error': 0
        }

        for i, token in enumerate(tokens, 1):
            try:
                print(f"\nChecking token {i}/30...")
                proxy = self.proxy_manager.get_proxy(token.strip())
                bot = DiscordBot(token.strip(), proxy)
                
                # 创建HTTP会话
                connector = aiohttp.TCPConnector(ssl=False)
                bot.session = aiohttp.ClientSession(connector=connector)
                
                # 检查账号状态
                is_valid, user_data = await bot.check_token_status()
                
                if is_valid:
                    results['valid'] += 1
                    valid_tokens.append(token)
                    print(f"✓ Token {i} VALID - Username: {user_data.get('username')}")
                else:
                    results['invalid'] += 1
                    print(f"✗ Token {i} INVALID")
                
                await bot.session.close()
                await asyncio.sleep(1)
                
            except Exception as e:
                results['error'] += 1
                print(f"! Token {i} ERROR: {str(e)}")

        print("\n=== Token Check Results ===")
        print(f"Valid tokens: {results['valid']}/30")
        print(f"Invalid tokens: {results['invalid']}/30")
        print(f"Errors: {results['error']}/30")
        
        return valid_tokens

async def main():
    """主函数"""
    try:
        logger.info("Starting Discord bot manager...")
        manager = BotManager()
        await manager.run()
    except Exception as e:
        logger.error(f"Critical error in main: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # 设置事件循环策略（Windows特定）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 运行主程序
    asyncio.run(main())