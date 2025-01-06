import random
import time
import asyncio
from typing import List, Any
from ..utils.logger import logger

class RateLimiter:
    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self.timestamps: List[float] = []

    async def acquire(self):
        """获取令牌，如果超过限制则等待"""
        now = time.time()
        
        # 清理过期的时间戳
        self.timestamps = [ts for ts in self.timestamps if ts > now - self.period]
        
        if len(self.timestamps) >= self.calls:
            sleep_time = self.timestamps[0] + self.period - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.timestamps.append(now)

class RetryHandler:
    @staticmethod
    async def retry_with_backoff(
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
        exceptions=(Exception,)
    ):
        """指数退避重试机制"""
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func()
            except exceptions as e:
                last_exception = e
                
                if attempt == max_retries - 1:
                    raise last_exception
                
                wait_time = min(delay * (backoff_factor ** attempt), max_delay)
                jitter = random.uniform(0, 0.1 * wait_time)
                total_wait = wait_time + jitter
                
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                logger.warning(f"Retrying in {total_wait:.2f}s...")
                
                await asyncio.sleep(total_wait)

class TokenBucket:
    """令牌桶限流器"""
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # 添加新令牌
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # 检查是否有足够的令牌
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
    """生成随机延迟时间"""
    return random.uniform(min_seconds, max_seconds)

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分割成固定大小的块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]