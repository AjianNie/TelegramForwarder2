import time
import asyncio
import logging

logger = logging.getLogger(__name__)

class TokenBucketRateLimiter:
    """
    一个基于 asyncio 的令牌桶速率限制器实现。
    这个实现是异步安全的 (thread-safe for asyncio tasks)。
    """
    def __init__(self, capacity: int, fill_rate: float):
        """
        构造一个令牌桶。

        Args:
            capacity (int): 桶容量，即最大允许的突发请求数。
            fill_rate (float): 每秒向桶中填充多少个令牌。
        """
        self.capacity = float(capacity)
        self.fill_rate = float(fill_rate)
        self.tokens = float(capacity)  # 初始时桶是满的
        self.last_fill_time = time.time()
        self.lock = asyncio.Lock()  # 用于保证令牌操作的原子性

    def _fill_tokens(self):
        """
        填充令牌。这是一个内部方法，在每次请求令牌时调用。
        """
        now = time.time()
        elapsed_time = now - self.last_fill_time
        
        if elapsed_time > 0:
            new_tokens = elapsed_time * self.fill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_fill_time = now

    async def get_token(self):
        """
        异步获取一个令牌。如果桶中没有令牌，则会等待直到有令牌为止。
        如果成功获取令牌，则返回 True。
        此方法是异步安全的。
        """
        async with self.lock:
            self._fill_tokens()  # 立即填充一次
            
            if self.tokens >= 1:
                self.tokens -= 1
                logger.debug("成功获取令牌，无需等待。")
                return True
            
            time_to_wait = (1 - self.tokens) / self.fill_rate
            wait_ms = time_to_wait + 0.01 
            
            logger.warning(f"触发API速率限制，需要等待 {wait_ms:.2f} 秒。")
            await asyncio.sleep(wait_ms)
            self._fill_tokens()
            if self.tokens >= 1:
                self.tokens -= 1
                logger.debug("等待后成功获取令牌。")
                return True
            logger.error("等待后仍然无法获取令牌，可能存在逻辑问题。")
            return False # 在极罕见情况下，如果等待后仍然没有令牌

# ==================== 全局单例 ====================
# 在这里定义全局的速率限制器实例，以便在整个应用中共享。
# 安全推荐值：容量为5，每秒填充3个令牌。
# 这意味着允许最多5个API调用的突发，之后会以每秒3个调用的速率平滑处理。
# 您可以根据实际情况和Telegram的限制调整这些值。
global_rate_limiter = TokenBucketRateLimiter(5, 3)

