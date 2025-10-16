# 标准库
import os
import asyncio
from typing import Optional, Any, Union, Dict
from contextlib import asynccontextmanager

# 第三方库
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from loguru import logger

# 自定义模块
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class RedisService:
    """Redis服务类
    
    提供Redis连接池管理、基础操作方法、健康检查和优雅降级机制。
    支持异步操作，与FastAPI项目架构保持一致。
    
    特性:
    - 异步连接池管理
    - 可选配置支持（Redis未配置时自动降级）
    - 完善的错误处理和重试机制
    - 健康检查和连接状态监控
    - 详细的日志记录
    """
    
    def __init__(self):
        """初始化Redis服务
        
        从环境变量读取配置，创建连接池。
        如果Redis配置不完整，将启用降级模式。
        """
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None
        self._is_available: bool = False
        self._degraded_mode: bool = False
        
        # 从环境变量读取配置
        self._host = os.getenv("REDIS_HOST", "localhost")
        self._port = int(os.getenv("REDIS_PORT", "6379"))
        self._password = os.getenv("REDIS_PASSWORD")
        self._db = int(os.getenv("REDIS_DB", "0"))
        self._max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
        
        # 连接超时配置
        self._socket_timeout = 5.0
        self._socket_connect_timeout = 5.0
        self._retry_on_timeout = True
        
        logger.info(f"Redis服务初始化 - Host: {self._host}:{self._port}, DB: {self._db}")
    
    async def initialize(self) -> bool:
        """初始化Redis连接池
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建连接池
            self._pool = ConnectionPool(
                host=self._host,
                port=self._port,
                password=self._password,
                db=self._db,
                max_connections=self._max_connections,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
                retry_on_timeout=self._retry_on_timeout,
                decode_responses=True,  # 自动解码响应为字符串
                encoding='utf-8'
            )
            
            # 创建Redis客户端
            self._redis = redis.Redis(connection_pool=self._pool)
            
            # 测试连接
            await self._redis.ping()
            self._is_available = True
            self._degraded_mode = False
            
            logger.success(f"Redis连接池初始化成功 - {self._host}:{self._port}")
            return True
            
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis连接失败，启用降级模式: {e}")
            self._degraded_mode = True
            self._is_available = False
            return False
            
        except Exception as e:
            logger.error(f"Redis初始化异常: {e}")
            self._degraded_mode = True
            self._is_available = False
            return False
    
    async def close(self) -> None:
        """关闭Redis连接池"""
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis连接池已关闭")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取Redis连接的上下文管理器
        
        Yields:
            redis.Redis: Redis连接实例
        """
        if not self._is_available:
            raise RedisError("Redis服务不可用，处于降级模式")
        
        try:
            yield self._redis
        except Exception as e:
            logger.error(f"Redis连接操作异常: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Redis健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        health_info = {
            "service": "redis",
            "status": "unknown",
            "degraded_mode": self._degraded_mode,
            "connection_info": {
                "host": self._host,
                "port": self._port,
                "db": self._db,
                "max_connections": self._max_connections
            },
            "error": None
        }
        
        if self._degraded_mode:
            health_info["status"] = "degraded"
            health_info["error"] = "Redis配置不可用，运行在降级模式"
            return health_info
        
        try:
            if not self._redis:
                await self.initialize()
            
            # 执行ping测试
            start_time = asyncio.get_event_loop().time()
            await self._redis.ping()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 获取Redis信息
            info = await self._redis.info()
            
            health_info.update({
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_seconds": info.get("uptime_in_seconds")
            })
            
            self._is_available = True
            logger.debug(f"Redis健康检查通过 - 响应时间: {response_time:.2f}ms")
            
        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["error"] = str(e)
            self._is_available = False
            logger.error(f"Redis健康检查失败: {e}")
        
        return health_info
    
    async def get(self, key: str) -> Optional[str]:
        """获取键值
        
        Args:
            key (str): Redis键名
            
        Returns:
            Optional[str]: 键对应的值，不存在返回None
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis GET操作 - key: {key}")
            return None
        
        try:
            async with self.get_connection() as conn:
                value = await conn.get(key)
                logger.debug(f"Redis GET成功 - key: {key}, value存在: {value is not None}")
                return value
                
        except Exception as e:
            logger.error(f"Redis GET操作失败 - key: {key}, error: {e}")
            # 发生错误时不抛出异常，返回None以支持降级
            return None
    
    async def set(
        self, 
        key: str, 
        value: Union[str, int, float], 
        ex: Optional[int] = None,
        nx: bool = False
    ) -> bool:
        """设置键值
        
        Args:
            key (str): Redis键名
            value (Union[str, int, float]): 要设置的值
            ex (Optional[int]): 过期时间（秒）
            nx (bool): 仅当键不存在时设置
            
        Returns:
            bool: 设置是否成功
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis SET操作 - key: {key}")
            return False
        
        try:
            async with self.get_connection() as conn:
                result = await conn.set(key, value, ex=ex, nx=nx)
                success = bool(result)
                logger.debug(f"Redis SET {'成功' if success else '失败'} - key: {key}, ex: {ex}, nx: {nx}")
                return success
                
        except Exception as e:
            logger.error(f"Redis SET操作失败 - key: {key}, error: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """删除键
        
        Args:
            *keys (str): 要删除的键名列表
            
        Returns:
            int: 成功删除的键数量
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis DELETE操作 - keys: {keys}")
            return 0
        
        try:
            async with self.get_connection() as conn:
                deleted_count = await conn.delete(*keys)
                logger.debug(f"Redis DELETE成功 - 删除了 {deleted_count} 个键")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Redis DELETE操作失败 - keys: {keys}, error: {e}")
            return 0
    
    async def exists(self, *keys: str) -> int:
        """检查键是否存在
        
        Args:
            *keys (str): 要检查的键名列表
            
        Returns:
            int: 存在的键数量
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis EXISTS操作 - keys: {keys}")
            return 0
        
        try:
            async with self.get_connection() as conn:
                exists_count = await conn.exists(*keys)
                logger.debug(f"Redis EXISTS检查完成 - {exists_count} 个键存在")
                return exists_count
                
        except Exception as e:
            logger.error(f"Redis EXISTS操作失败 - keys: {keys}, error: {e}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间
        
        Args:
            key (str): Redis键名
            seconds (int): 过期时间（秒）
            
        Returns:
            bool: 设置是否成功
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis EXPIRE操作 - key: {key}")
            return False
        
        try:
            async with self.get_connection() as conn:
                result = await conn.expire(key, seconds)
                success = bool(result)
                logger.debug(f"Redis EXPIRE {'成功' if success else '失败'} - key: {key}, seconds: {seconds}")
                return success
                
        except Exception as e:
            logger.error(f"Redis EXPIRE操作失败 - key: {key}, error: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """获取键的剩余生存时间
        
        Args:
            key (str): Redis键名
            
        Returns:
            int: 剩余生存时间（秒），-1表示永不过期，-2表示键不存在
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis TTL操作 - key: {key}")
            return -2
        
        try:
            async with self.get_connection() as conn:
                ttl_value = await conn.ttl(key)
                logger.debug(f"Redis TTL查询完成 - key: {key}, ttl: {ttl_value}")
                return ttl_value
                
        except Exception as e:
            logger.error(f"Redis TTL操作失败 - key: {key}, error: {e}")
            return -2
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """递增键的值
        
        Args:
            key (str): Redis键名
            amount (int): 递增量，默认为1
            
        Returns:
            Optional[int]: 递增后的值，失败返回None
        """
        if self._degraded_mode:
            logger.debug(f"降级模式: 跳过Redis INCR操作 - key: {key}")
            return None
        
        try:
            async with self.get_connection() as conn:
                new_value = await conn.incr(key, amount)
                logger.debug(f"Redis INCR成功 - key: {key}, amount: {amount}, new_value: {new_value}")
                return new_value
                
        except Exception as e:
            logger.error(f"Redis INCR操作失败 - key: {key}, error: {e}")
            return None
    
    @property
    def is_available(self) -> bool:
        """Redis服务是否可用"""
        return self._is_available
    
    @property
    def is_degraded(self) -> bool:
        """是否处于降级模式"""
        return self._degraded_mode
    
    def __repr__(self) -> str:
        """字符串表示"""
        status = "可用" if self._is_available else "降级模式"
        return f"RedisService(host={self._host}:{self._port}, db={self._db}, status={status})"


# 全局Redis服务实例
redis_service = RedisService()


async def get_redis_service() -> RedisService:
    """获取Redis服务实例
    
    用于FastAPI依赖注入
    
    Returns:
        RedisService: Redis服务实例
    """
    if not redis_service.is_available and not redis_service.is_degraded:
        await redis_service.initialize()
    return redis_service


# 应用启动时初始化Redis服务
async def init_redis_service():
    """初始化Redis服务
    
    在应用启动时调用，确保Redis连接池正确初始化
    """
    logger.info("正在初始化Redis服务...")
    success = await redis_service.initialize()
    if success:
        logger.success("Redis服务初始化完成")
    else:
        logger.warning("Redis服务初始化失败，将在降级模式下运行")


# 应用关闭时清理Redis连接
async def cleanup_redis_service():
    """清理Redis服务
    
    在应用关闭时调用，确保连接池正确关闭
    """
    logger.info("正在关闭Redis服务...")
    await redis_service.close()
    logger.info("Redis服务已关闭")