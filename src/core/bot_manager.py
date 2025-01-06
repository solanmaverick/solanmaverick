import asyncio
import random
from typing import List, Dict, Optional
from datetime import datetime
from utils.logger import logger
from utils.config import config
from .bot import DiscordBot

class BotManager:
    def __init__(self):
        self.tokens: List[str] = []
        self.proxies: List[Dict[str, str]] = []
        self.active_bots: List[DiscordBot] = []
        self.current_batch_index = 0
        self.batch_size = 5
        self.running = True

    async def load_resources(self):
        """Load tokens and proxies from files"""
        try:
            # Load tokens
            with open('data/tokens.txt', 'r') as f:
                self.tokens = [line.strip() for line in f if line.strip()]
            
            # Load and format proxies
            with open('data/proxies.txt', 'r') as f:
                proxy_lines = [line.strip() for line in f if line.strip()]
                for proxy in proxy_lines:
                    host, port, username, password = proxy.split(':')
                    self.proxies.append({
                        'url': f'http://{username}:{password}@{host}:{port}',
                        'host': host,
                        'port': port,
                        'username': username,
                        'password': password
                    })
            
            logger.info(f"Loaded {len(self.tokens)} tokens and {len(self.proxies)} proxies")
            
        except Exception as e:
            logger.error(f"Failed to load resources: {str(e)}")
            raise

    def get_next_batch(self) -> List[tuple]:
        """Get next batch of tokens and proxies"""
        start_idx = self.current_batch_index * self.batch_size
        end_idx = start_idx + self.batch_size
        
        if start_idx >= len(self.tokens):
            self.current_batch_index = 0
            start_idx = 0
            end_idx = self.batch_size
            
        batch_tokens = self.tokens[start_idx:end_idx]
        batch_proxies = self.proxies[start_idx:end_idx]
        
        self.current_batch_index += 1
        return list(zip(batch_tokens, batch_proxies))

    async def initialize_bot(self, token: str, proxy: Dict[str, str]) -> Optional[DiscordBot]:
        """Initialize a single bot"""
        try:
            bot = DiscordBot(token=token, proxy=proxy)
            await bot.initialize()
            await bot.connect()
            return bot
        except Exception as e:
            logger.error(f"Failed to initialize bot: {str(e)}")
            return None

    async def check_batch_limits(self) -> bool:
        """Check if current batch has reached message limits"""
        limit_reached_count = 0
        total_bots = len(self.active_bots)
        if total_bots == 0:
            return False
            
        for bot in self.active_bots:
            if not await bot.daily_tasks.can_send_message():
                if hasattr(bot, 'user_data') and bot.user_data:
                    logger.info(f"Bot {bot.user_data.get('username', 'unknown')} reached daily limit")
                limit_reached_count += 1
                
        threshold_reached = limit_reached_count >= total_bots * 0.6
        if threshold_reached:
            logger.info(f"{limit_reached_count}/{total_bots} bots reached daily limit (60% threshold reached)")
        return threshold_reached

    async def cleanup_batch(self):
        """Cleanup current batch of bots"""
        for bot in self.active_bots:
            try:
                await bot.close()
            except Exception as e:
                logger.error(f"Error closing bot: {str(e)}")
        self.active_bots.clear()

    async def run_batch(self, batch: List[tuple]):
        """Run a batch of bots with smooth transition"""
        # Initialize new bots
        new_bots = []
        for token, proxy in batch:
            bot = await self.initialize_bot(token, proxy)
            if bot:
                new_bots.append(bot)
                await asyncio.sleep(random.uniform(2, 5))  # Stagger bot initialization
                if hasattr(bot, 'user_data') and bot.user_data:
                    logger.info(f"Bot {bot.user_data.get('username', 'unknown')} initialized and connected")
                else:
                    logger.info("Bot initialized and connected (username unknown)")

        if not new_bots:
            logger.error("No bots could be initialized in this batch")
            return

        # Perform gradual transition if there are existing active bots
        if self.active_bots:
            logger.info("Starting gradual transition to new batch...")
            old_bots = self.active_bots.copy()
            for old_bot in old_bots:
                # Remove old bot
                await old_bot.close()
                self.active_bots.remove(old_bot)
                
                # Add new bot if available
                if new_bots:
                    new_bot = new_bots.pop(0)
                    self.active_bots.append(new_bot)
                    
                # Add transition delay
                await asyncio.sleep(random.uniform(5, 10))
        else:
            # No existing bots, just add all new bots
            self.active_bots.extend(new_bots)
            new_bots.clear()

        try:
            while self.running:
                # Check if batch has reached limit threshold
                if await self.check_batch_limits():
                    logger.info("Batch limit threshold reached (60%), rotating to next batch")
                    break

                # Wait before checking again
                await asyncio.sleep(300)  # Check every 5 minutes

        except Exception as e:
            logger.error(f"Error in batch run: {str(e)}")
        finally:
            await self.cleanup_batch()

    async def run(self):
        """Main run loop"""
        try:
            await self.load_resources()
            
            while self.running:
                batch = self.get_next_batch()
                logger.info(f"Starting new batch with {len(batch)} bots")
                
                await self.run_batch(batch)
                
                # Add delay between batches
                await asyncio.sleep(random.uniform(30, 60))
                
        except Exception as e: 
            logger.error(f"Bot manager error: {str(e)}")
        finally:
            self.running = False
            await self.cleanup_batch()

    async def stop(self):
        """Stop the bot manager"""
        self.running = False
        await self.cleanup_batch()
