# 标准库
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
import time
import json

# 第三方库
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_
from loguru import logger

# 自定义模块
from .service_models import Message, MessageRecipient
from .redis_service import RedisService


class MessageService:
    """消息业务逻辑层
    提供发送、查询、状态更新与删除操作。
    支持单接收者和多接收者消息发送，集成Redis缓存功能。
    接口保持 async 以与项目其他服务一致，内部使用同步 Session。
    """

    def __init__(self, redis_service: Optional[RedisService] = None):
        """初始化消息服务
        
        Args:
            redis_service: Redis服务实例，用于缓存功能
        """
        self.redis_service = redis_service
        # Redis缓存键前缀
        self.CACHE_PREFIX_MESSAGES = "messages:user:"
        self.CACHE_PREFIX_UNREAD_COUNT = "unread_count:user:"
        # 缓存过期时间（秒）
        self.CACHE_EXPIRE_TIME = 300  # 5分钟

    async def send_message(
        self,
        db: Session,
        sender_id: int,
        recipient_ids: List[int],
        title: str,
        content: str,
    ) -> Message:
        """发送消息给多个接收者
        
        Args:
            db: 数据库会话
            sender_id: 发送者ID
            recipient_ids: 接收者ID列表
            title: 消息标题
            content: 消息内容
            
        Returns:
            Message: 创建的消息对象
            
        Raises:
            Exception: 发送失败时抛出异常
        """
        # 调用多接收者方法
        return await self.send_message_to_multiple(
            db=db,
            sender_id=sender_id,
            recipient_ids=recipient_ids,
            title=title,
            content=content
        )

    async def send_message_to_multiple(
        self,
        db: Session,
        sender_id: int,
        recipient_ids: List[int],
        title: str,
        content: str,
    ) -> Message:
        """发送消息（支持多接收者）
        
        Args:
            db: 数据库会话
            sender_id: 发送者ID
            recipient_ids: 接收者ID列表
            title: 消息标题
            content: 消息内容
            
        Returns:
            Message: 创建的消息对象
            
        Raises:
            Exception: 发送失败时抛出异常
        """
        if not recipient_ids:
            raise ValueError("接收者列表不能为空")
        
        # 去重接收者ID
        unique_recipient_ids = list(set(recipient_ids))
        
        try:
            # 开始数据库事务
            # 1. 创建主消息记录（移除receiver_id字段）
            msg = Message(
                sender_id=sender_id,
                title=title,
                content=content,
                is_read=False,
                created_at=datetime.utcnow(),
            )
            db.add(msg)
            db.flush()  # 获取消息ID，但不提交事务
            
            # 2. 批量创建消息接收者记录
            message_recipients = []
            for recipient_id in unique_recipient_ids:
                recipient = MessageRecipient(
                    message_id=msg.id,
                    recipient_id=recipient_id,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                message_recipients.append(recipient)
            
            # 批量插入接收者记录
            db.add_all(message_recipients)
            
            # 提交事务
            db.commit()
            db.refresh(msg)
            
            logger.info(f"多接收者消息发送成功 id={msg.id} sender={sender_id} -> recipients={unique_recipient_ids}")
            
            # 3. 更新Redis缓存（异步处理，失败不影响主流程）
            await self._update_cache_after_send(unique_recipient_ids, msg)
            
            return msg
            
        except Exception as e:
            db.rollback()
            logger.error(f"多接收者消息发送失败: {e}")
    async def _update_cache_after_read(self, user_id: int, message_ids: List[int]) -> None:
        """标记已读后更新缓存
        
        Args:
            user_id: 用户ID
            message_ids: 已读消息ID列表
        """
        if not self.redis_service:
            return
            
        try:
            # 清除相关的消息列表缓存
            cache_patterns = [
                f"{self.MESSAGE_LIST_CACHE_PREFIX}:{user_id}:*",
                f"{self.MESSAGE_LIST_CACHE_PREFIX}:recent:{user_id}:*"
            ]
            
            for pattern in cache_patterns:
                # 获取匹配的键
                keys = await self.redis_service.keys(pattern)
                if keys:
                    await self.redis_service.delete(*keys)
            
            # 减少未读消息计数
            unread_cache_key = f"{self.UNREAD_COUNT_CACHE_PREFIX}:{user_id}"
            current_count = await self.redis_service.get(unread_cache_key)
            
            if current_count is not None:
                try:
                    count = int(current_count)
                    new_count = max(0, count - len(message_ids))
                    await self.redis_service.set(
                        unread_cache_key, 
                        str(new_count), 
                        ex=self.CACHE_EXPIRE_TIME
                    )
                    logger.debug(f"更新用户{user_id}未读消息计数: {count} -> {new_count}")
                except ValueError:
                    # 如果计数值无效，删除缓存
                    await self.redis_service.delete(unread_cache_key)
            
            logger.debug(f"标记已读后缓存更新完成 - 用户:{user_id}, 消息数:{len(message_ids)}")
            
        except Exception as e:
            logger.warning(f"标记已读后更新缓存失败: {e}")

    async def get_message_statistics(self, user_id: int) -> dict:
        """获取用户消息统计信息（支持缓存）
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 消息统计信息
        """
        import time
        start_time = time.time()
        
        try:
            cache_key = f"{self.MESSAGE_LIST_CACHE_PREFIX}:stats:{user_id}"
            
            # 尝试从缓存获取
            if self.redis_service:
                cached_stats = await self.redis_service.get(cache_key)
                if cached_stats:
                    import json
                    stats = json.loads(cached_stats)
                    query_time = time.time() - start_time
                    logger.info(f"从缓存获取消息统计 - 用户:{user_id}, 耗时:{query_time:.3f}s")
                    return stats
            
            # 从数据库查询统计信息
            base_query = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id
            )
            
            total_count = base_query.count()
            unread_count = base_query.filter(MessageRecipient.is_read == False).count()
            read_count = total_count - unread_count
            
            # 按消息类型统计
            type_stats = {}
            type_query = self.db.query(
                Message.message_type,
                func.count(MessageRecipient.id).label('count')
            ).join(
                MessageRecipient, Message.id == MessageRecipient.message_id
            ).filter(
                MessageRecipient.recipient_id == user_id
            ).group_by(Message.message_type).all()
            
            for msg_type, count in type_query:
                type_stats[msg_type] = count
            
            stats = {
                'total_count': total_count,
                'unread_count': unread_count,
                'read_count': read_count,
                'type_statistics': type_stats,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 缓存统计结果（使用较短的过期时间）
            if self.redis_service:
                import json
                await self.redis_service.set(
                    cache_key,
                    json.dumps(stats, ensure_ascii=False),
                    ex=300  # 5分钟过期
                )
            
            query_time = time.time() - start_time
            logger.info(f"从数据库获取消息统计 - 用户:{user_id}, 总数:{total_count}, 未读:{unread_count}, 耗时:{query_time:.3f}s")
            
            return stats
            
        except Exception as e:
            query_time = time.time() - start_time
            logger.error(f"获取消息统计失败 - 用户:{user_id}, 耗时:{query_time:.3f}s, 错误:{e}")
            raise e

    async def _log_performance(self, operation: str, duration: float, details: dict = None):
        """记录性能日志"""
        try:
            log_data = {
                "operation": operation,
                "duration_ms": round(duration * 1000, 2),
                "timestamp": datetime.now().isoformat()
            }
            
            if details:
                log_data.update(details)
            
            # 性能警告阈值
            if duration > 1.0:  # 超过1秒
                logger.warning(f"慢查询警告: {operation} 耗时 {duration:.2f}s", extra=log_data)
            elif duration > 0.5:  # 超过500ms
                logger.info(f"性能监控: {operation} 耗时 {duration:.2f}s", extra=log_data)
            else:
                logger.debug(f"性能监控: {operation} 耗时 {duration:.2f}s", extra=log_data)
                
        except Exception as e:
            logger.error(f"记录性能日志失败: {e}")

    async def _log_cache_metrics(self, operation: str, cache_key: str, hit: bool, data_size: int = 0):
        """记录缓存指标"""
        try:
            metrics = {
                "operation": operation,
                "cache_key": cache_key,
                "cache_hit": hit,
                "data_size": data_size,
                "timestamp": datetime.now().isoformat()
            }
            
            if hit:
                logger.debug(f"缓存命中: {operation} - {cache_key}", extra=metrics)
            else:
                logger.debug(f"缓存未命中: {operation} - {cache_key}", extra=metrics)
                
        except Exception as e:
            logger.error(f"记录缓存指标失败: {e}")

    async def _log_database_metrics(self, operation: str, query_type: str, affected_rows: int = 0, execution_time: float = 0):
        """记录数据库操作指标"""
        try:
            metrics = {
                "operation": operation,
                "query_type": query_type,
                "affected_rows": affected_rows,
                "execution_time_ms": round(execution_time * 1000, 2),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.debug(f"数据库操作: {operation} - {query_type}", extra=metrics)
            
        except Exception as e:
            logger.error(f"记录数据库指标失败: {e}")

    async def get_service_health_metrics(self) -> dict:
        """获取服务健康指标"""
        try:
            start_time = time.time()
            
            # 测试数据库连接
            db_healthy = True
            db_response_time = 0
            try:
                db_start = time.time()
                # 简单查询测试数据库连接
                self.db.execute("SELECT 1").fetchone()
                db_response_time = time.time() - db_start
            except Exception as e:
                db_healthy = False
                logger.error(f"数据库健康检查失败: {e}")
            
            # 测试Redis连接
            redis_healthy = True
            redis_response_time = 0
            try:
                redis_start = time.time()
                await self.redis_service.ping()
                redis_response_time = time.time() - redis_start
            except Exception as e:
                redis_healthy = False
                logger.error(f"Redis健康检查失败: {e}")
            
            total_time = time.time() - start_time
            
            metrics = {
                "service": "MessageService",
                "healthy": db_healthy and redis_healthy,
                "database": {
                    "healthy": db_healthy,
                    "response_time_ms": round(db_response_time * 1000, 2)
                },
                "redis": {
                    "healthy": redis_healthy,
                    "response_time_ms": round(redis_response_time * 1000, 2)
                },
                "total_check_time_ms": round(total_time * 1000, 2),
                "timestamp": datetime.now().isoformat()
            }
            
            await self._log_performance("health_check", total_time, metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"获取服务健康指标失败: {e}")
            return {
                "service": "MessageService",
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def search_messages(
        self,
        user_id: int,
        keyword: str,
        message_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[dict], int]:
        """搜索用户消息（支持关键词搜索）
        
        Args:
            user_id: 用户ID
            keyword: 搜索关键词
            message_type: 消息类型过滤
            is_read: 是否已读过滤
            page: 页码
            page_size: 每页大小
            
        Returns:
            Tuple[List[dict], int]: 搜索结果和总数
        """
        import time
        start_time = time.time()
        
        try:
            # 构建查询
            query = self.db.query(MessageRecipient).join(Message).filter(
                MessageRecipient.recipient_id == user_id
            )
            
            # 关键词搜索（标题和内容）
            if keyword:
                search_filter = or_(
                    Message.title.contains(keyword),
                    Message.content.contains(keyword)
                )
                query = query.filter(search_filter)
            
            # 添加其他过滤条件
            if message_type:
                query = query.filter(Message.message_type == message_type)
            if is_read is not None:
                query = query.filter(MessageRecipient.is_read == is_read)
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            offset = (page - 1) * page_size
            messages = query.options(
                joinedload(MessageRecipient.message).joinedload(Message.sender)
            ).order_by(
                MessageRecipient.created_at.desc()
            ).offset(offset).limit(page_size).all()
            
            # 转换为字典格式
            messages_data = []
            for mr in messages:
                msg = mr.message
                msg_dict = {
                    'id': msg.id,
                    'title': msg.title,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'message_type': msg.message_type,
                    'is_read': mr.is_read,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    'sender_name': msg.sender.username if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None,
                    'recipient_read_at': mr.read_at.isoformat() if mr.read_at else None
                }
                messages_data.append(msg_dict)
            
            query_time = time.time() - start_time
            logger.info(f"搜索消息完成 - 用户:{user_id}, 关键词:'{keyword}', 结果:{len(messages_data)}/{total}, 耗时:{query_time:.3f}s")
            
            return messages_data, total
            
        except Exception as e:
            query_time = time.time() - start_time
            logger.error(f"搜索消息失败 - 用户:{user_id}, 关键词:'{keyword}', 耗时:{query_time:.3f}s, 错误:{e}")
            raise e

    async def _update_cache_after_send(self, recipient_ids: List[int], message: Message) -> None:
        """发送消息后更新Redis缓存
        
        Args:
            recipient_ids: 接收者ID列表
            message: 消息对象
        """
        if not self.redis_service:
            return
            
        try:
            # 为每个接收者更新缓存
            for recipient_id in recipient_ids:
                # 1. 清除消息列表缓存（让下次查询重新从数据库获取）
                cache_key_messages = f"{self.CACHE_PREFIX_MESSAGES}{recipient_id}"
                await self.redis_service.delete(cache_key_messages)
                
                # 2. 增加未读消息数量
                cache_key_unread = f"{self.CACHE_PREFIX_UNREAD_COUNT}{recipient_id}"
                await self.redis_service.increment(cache_key_unread)
                await self.redis_service.expire(cache_key_unread, self.CACHE_EXPIRE_TIME)
                
            logger.debug(f"消息发送后缓存更新成功，接收者: {recipient_ids}")
            
        except Exception as e:
            # Redis操作失败不影响主流程，仅记录日志
            logger.warning(f"消息发送后缓存更新失败: {e}")

    async def list_messages(
        self,
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
        message_type: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """查询用户消息列表（支持Redis缓存和消息类型过滤）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页大小
            is_read: 是否已读筛选
            message_type: 消息类型过滤
            
        Returns:
            Tuple[List[dict], int]: 消息字典列表和总数
        """
        import time
        start_time = time.time()
        
        try:
            # 1. 尝试从Redis缓存获取
            cache_key = f"{self.CACHE_PREFIX_MESSAGES}{user_id}:page_{page}:size_{page_size}:read_{is_read}:type_{message_type}"
            cached_result = await self._get_cached_messages(cache_key)
            
            if cached_result:
                messages_data, total = cached_result
                query_time = time.time() - start_time
                logger.info(f"从缓存获取消息列表 - 用户:{user_id}, 页码:{page}, 耗时:{query_time:.3f}s")
                return messages_data, total
            
            # 2. 从数据库查询（使用新的MessageRecipient表）
            # 通过message_recipients表查询用户的消息
            query = db.query(MessageRecipient).join(
                Message, MessageRecipient.message_id == Message.id
            ).filter(MessageRecipient.recipient_id == user_id)
            
            if is_read is not None:
                query = query.filter(MessageRecipient.is_read == is_read)
            if message_type:
                query = query.filter(Message.message_type == message_type)

            total = query.count()
            query = query.order_by(MessageRecipient.created_at.desc())

            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 20
            if page_size > 100:
                page_size = 100

            recipients = query.offset((page - 1) * page_size).limit(page_size).all()
            
            # 3. 转换为字典格式返回
            messages_data = []
            for recipient in recipients:
                msg = recipient.message
                msg_dict = {
                    'id': msg.id,
                    'title': msg.title,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'message_type': msg.message_type,
                    'is_read': recipient.is_read,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    'updated_at': msg.updated_at.isoformat() if msg.updated_at else None,
                    'sender_name': msg.sender.username if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None,
                    'recipient_read_at': recipient.read_at.isoformat() if recipient.read_at else None
                }
                messages_data.append(msg_dict)
            
            # 4. 缓存查询结果
            message_objects = [recipient.message for recipient in recipients]
            await self._cache_messages(cache_key, message_objects, total)
            
            query_time = time.time() - start_time
            logger.info(f"从数据库获取消息列表 - 用户:{user_id}, 页码:{page}, 总数:{total}, 耗时:{query_time:.3f}s")
            
            return messages_data, total
        except Exception as e:
                    logger.warning(f"从数据库获取消息列表失败: {e}")    
    async def get_recent_messages(
        self, 
        user_id: int, 
        limit: int = 10,
        message_type: Optional[str] = None
    ) -> List[dict]:
        """获取用户最近的消息（支持缓存）
        
        Args:
            user_id: 用户ID
            limit: 限制数量，默认10条
            message_type: 消息类型过滤
            
        Returns:
            List[dict]: 最近消息字典列表
        """
        import time
        start_time = time.time()
        
        try:
            # 构建缓存键
            cache_key = f"{self.MESSAGE_LIST_CACHE_PREFIX}:recent:{user_id}:{limit}:{message_type}"
            
            # 尝试从缓存获取
            cached_result = await self._get_cached_messages(cache_key)
            if cached_result:
                messages_data, _ = cached_result
                query_time = time.time() - start_time
                logger.info(f"从缓存获取最近消息 - 用户:{user_id}, 数量:{len(messages_data)}, 耗时:{query_time:.3f}s")
                return messages_data[:limit]  # 确保不超过限制数量
            
            # 从数据库查询
            query = self.db.query(MessageRecipient).join(Message).filter(
                MessageRecipient.recipient_id == user_id
            )
            
            # 添加消息类型过滤
            if message_type:
                query = query.filter(Message.message_type == message_type)
            
            # 按创建时间倒序，获取最近的消息
            messages = query.options(
                joinedload(MessageRecipient.message).joinedload(Message.sender)
            ).order_by(
                MessageRecipient.created_at.desc()
            ).limit(limit).all()
            
            # 转换为字典格式
            messages_data = []
            for mr in messages:
                msg = mr.message
                msg_dict = {
                    'id': msg.id,
                    'title': msg.title,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'message_type': msg.message_type,
                    'is_read': mr.is_read,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    'updated_at': msg.updated_at.isoformat() if msg.updated_at else None,
                    'sender_name': msg.sender.username if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None,
                    'recipient_read_at': mr.read_at.isoformat() if mr.read_at else None
                }
                messages_data.append(msg_dict)
            
            # 缓存结果（使用较短的过期时间，因为是最近消息）
            message_objects = [mr.message for mr in messages]
            await self._cache_messages(cache_key, message_objects, len(messages_data))
            
            query_time = time.time() - start_time
            logger.info(f"从数据库获取最近消息 - 用户:{user_id}, 数量:{len(messages_data)}, 耗时:{query_time:.3f}s")
            
            return messages_data
            
        except Exception as e:
            query_time = time.time() - start_time
            logger.error(f"获取最近消息失败 - 用户:{user_id}, 耗时:{query_time:.3f}s, 错误:{e}")
            raise e

    async def mark_messages_as_read(
        self, 
        user_id: int, 
        message_ids: List[int]
    ) -> int:
        """批量标记消息为已读
        
        Args:
            user_id: 用户ID
            message_ids: 消息ID列表
            
        Returns:
            int: 成功标记的消息数量
        """
        start_time = time.time()
        
        if not message_ids:
            return 0
        
        # 使用事务确保数据一致性
        transaction = self.db.begin()
        try:
            current_time = datetime.now(timezone.utc)
            
            # 批量更新MessageRecipient表
            updated_recipients = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id,
                MessageRecipient.message_id.in_(message_ids),
                MessageRecipient.is_read == False
            ).update(
                {
                    'is_read': True,
                    'read_at': current_time
                },
                synchronize_session=False
            )
            
            # 提交事务
            transaction.commit()
            
            # 异步更新Redis缓存
            try:
                await self._update_cache_after_read(user_id, message_ids)
            except Exception as cache_error:
                logger.warning(f"缓存更新失败，但数据库操作成功 - 用户:{user_id}, 错误:{cache_error}")
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("mark_messages_as_read", duration, {
                "user_id": user_id,
                "message_count": len(message_ids),
                "updated_count": updated_recipients,
                "success": True
            })
            
            logger.info(f"批量标记消息已读 - 用户:{user_id}, 消息数:{len(message_ids)}, 成功:{updated_recipients}, 耗时:{duration:.3f}s")
            
            return updated_recipients
            
        except Exception as e:
            transaction.rollback()
            duration = time.time() - start_time
            
            # 记录错误性能指标
            self._log_performance("mark_messages_as_read", duration, {
                "user_id": user_id,
                "message_count": len(message_ids),
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"批量标记消息已读失败 - 用户:{user_id}, 消息数:{len(message_ids)}, 耗时:{duration:.3f}s, 错误:{e}")
            raise e

    async def _get_cached_messages(self, cache_key: str) -> Optional[Tuple[List[dict], int]]:
        """从Redis获取缓存的消息列表
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Optional[Tuple[List[dict], int]]: 缓存的消息字典列表和总数，如果不存在返回None
        """
        if not self.redis_service:
            return None
            
        try:
            start_time = time.time()
            cached_data = await self.redis_service.get(cache_key)
            duration = time.time() - start_time
            
            if cached_data:
                data = json.loads(cached_data)
                messages_data = data.get('messages', [])
                total = data.get('total', 0)
                
                await self._log_cache_metrics("get_cached_messages", cache_key, True, len(cached_data))
                await self._log_performance("get_cached_messages", duration, {
                    "cache_key": cache_key,
                    "message_count": len(messages_data),
                    "total": total,
                    "data_size": len(cached_data)
                })
                
                logger.debug(f"从缓存获取消息列表成功，共{len(messages_data)}条消息")
                return messages_data, total
            else:
                await self._log_cache_metrics("get_cached_messages", cache_key, False)
                await self._log_performance("get_cached_messages", duration, {
                    "cache_key": cache_key,
                    "cache_miss": True
                })
                return None
        except Exception as e:
            logger.warning(f"获取缓存消息列表失败: {e}")
            return None

    async def _cache_messages(self, cache_key: str, messages: List[Message], total: int) -> None:
        """缓存消息列表到Redis
        
        Args:
            cache_key: 缓存键
            messages: 消息列表
            total: 总数
        """
        if not self.redis_service:
            return
            
        try:
            start_time = time.time()
            
            # 将Message对象转换为可序列化的字典
            messages_data = []
            for msg in messages:
                msg_dict = {
                    'id': msg.id,
                    'title': msg.title,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'message_type': msg.message_type,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    # 添加发送者信息（如果存在）
                    'sender_name': msg.sender.username if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None
                }
                messages_data.append(msg_dict)
            
            cache_data = {
                'messages': messages_data,
                'total': total,
                'cached_at': datetime.utcnow().isoformat()
            }
            
            serialized_data = json.dumps(cache_data, ensure_ascii=False)
            await self.redis_service.set(
                cache_key, 
                serialized_data, 
                ex=self.CACHE_EXPIRE_TIME
            )
            
            duration = time.time() - start_time
            await self._log_cache_metrics("cache_messages", cache_key, True, len(serialized_data))
            await self._log_performance("cache_messages", duration, {
                "cache_key": cache_key,
                "message_count": len(messages_data),
                "total": total,
                "data_size": len(serialized_data),
                "expire_time": self.CACHE_EXPIRE_TIME
            })
            
            logger.debug(f"缓存消息列表成功，共{len(messages_data)}条消息")
            
        except Exception as e:
            duration = time.time() - start_time if 'start_time' in locals() else 0
            await self._log_performance("cache_messages_error", duration, {
                "cache_key": cache_key,
                "error": str(e)
            })
            logger.warning(f"缓存消息列表失败: {e}")

    async def get_unread_count(self, db: Session, user_id: int) -> int:
        """获取用户未读消息数量（支持Redis缓存）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            int: 未读消息数量
        """
        try:
            # 1. 尝试从Redis缓存获取
            cache_key = f"{self.CACHE_PREFIX_UNREAD_COUNT}{user_id}"
            if self.redis_service:
                cached_count = await self.redis_service.get(cache_key)
                if cached_count is not None:
                    try:
                        count = int(cached_count)
                        logger.debug(f"从缓存获取未读消息数量成功 user_id={user_id}, count={count}")
                        return count
                    except (ValueError, TypeError):
                        pass
            
            # 2. 从数据库查询
            count = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.is_read == False
                )
            ).count()
            
            # 3. 缓存结果
            if self.redis_service:
                try:
                    await self.redis_service.set(cache_key, str(count), expire=self.CACHE_EXPIRE_TIME)
                except Exception as e:
                    logger.warning(f"缓存未读消息数量失败: {e}")
            
            return count
            
        except Exception as e:
            logger.error(f"获取未读消息数量失败: {e}")
            raise e

    async def mark_read(self, db: Session, user_id: int, message_id: int) -> bool:
        """标记消息为已读（更新MessageRecipient表）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            message_id: 消息ID
            
        Returns:
            bool: 是否标记成功
        """
        try:
            # 查找对应的MessageRecipient记录
            recipient = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.message_id == message_id,
                    MessageRecipient.recipient_id == user_id
                )
            ).first()
            
            if not recipient:
                return False
                
            if recipient.is_read:
                return True
                
            # 标记为已读
            recipient.mark_as_read()
            
            db.commit()
            
            # 更新Redis缓存
            await self._update_cache_after_read(user_id)
            
            logger.info(f"消息标记已读成功 message_id={message_id} user_id={user_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"标记消息已读失败: {e}")
            raise e

    async def mark_all_read(self, db: Session, user_id: int) -> int:
        """标记用户所有消息为已读
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            int: 标记的消息数量
        """
        try:
            # 更新MessageRecipient表
            affected = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.is_read == False
                )
            ).update(
                {
                    MessageRecipient.is_read: True,
                    MessageRecipient.read_at: datetime.now(timezone.utc)
                },
                synchronize_session=False
            )
            
            db.commit()
            
            # 更新Redis缓存
            await self._update_cache_after_read(user_id)
            
            logger.info(f"全部消息标记已读成功 user_id={user_id}, affected={affected}")
            return affected or 0
            
        except Exception as e:
            db.rollback()
            logger.error(f"全部标记已读失败: {e}")
            raise e

    async def _update_cache_after_read(self, user_id: int) -> None:
        """标记已读后更新Redis缓存
        
        Args:
            user_id: 用户ID
        """
        if not self.redis_service:
            return
            
        try:
            # 清除相关缓存，让下次查询重新从数据库获取
            cache_key_messages = f"{self.CACHE_PREFIX_MESSAGES}{user_id}"
            cache_key_unread = f"{self.CACHE_PREFIX_UNREAD_COUNT}{user_id}"
            
            await self.redis_service.delete(cache_key_messages)
            await self.redis_service.delete(cache_key_unread)
            
            logger.debug(f"标记已读后缓存清除成功 user_id={user_id}")
            
        except Exception as e:
            logger.warning(f"标记已读后缓存更新失败: {e}")

    async def delete_message(self, db: Session, user_id: int, message_id: int) -> bool:
        """删除用户的消息接收记录
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            message_id: 消息ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 删除MessageRecipient记录
            recipient = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.message_id == message_id,
                    MessageRecipient.recipient_id == user_id
                )
            ).first()
            
            if not recipient:
                return False
                
            db.delete(recipient)
            
            # 检查是否还有其他接收者，如果没有则删除主消息
            remaining_recipients = db.query(MessageRecipient).filter(
                MessageRecipient.message_id == message_id
            ).count()
            
            if remaining_recipients == 1:  # 只剩当前要删除的记录
                message = db.query(Message).filter(Message.id == message_id).first()
                if message:
                    db.delete(message)
            
            db.commit()
            
            # 更新Redis缓存
            await self._update_cache_after_read(user_id)
            
            logger.info(f"消息删除成功 message_id={message_id} user_id={user_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"删除消息失败: {e}")
            raise e

    async def delete_by_type(self, db: Session, user_id: int, type_: str) -> int:
        """按类型批量删除用户消息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            type_: 删除类型 ("read", "unread", "all")
            
        Returns:
            int: 删除的消息数量
        """
        try:
            query = db.query(MessageRecipient).filter(MessageRecipient.recipient_id == user_id)
            
            if type_ == "read":
                query = query.filter(MessageRecipient.is_read == True)
            elif type_ == "unread":
                query = query.filter(MessageRecipient.is_read == False)
            elif type_ == "all":
                pass
            else:
                raise ValueError("type 必须为 read、unread 或 all")

            # 获取要删除的消息ID列表
            message_ids = [r.message_id for r in query.all()]
            
            # 执行删除
            deleted = query.delete(synchronize_session=False)
            
            # 清理没有接收者的消息
            for message_id in message_ids:
                remaining = db.query(MessageRecipient).filter(
                    MessageRecipient.message_id == message_id
                ).count()
                if remaining == 0:
                    db.query(Message).filter(Message.id == message_id).delete()
            
            db.commit()
            
            # 更新Redis缓存
            await self._update_cache_after_read(user_id)
            
            logger.info(f"批量删除消息成功 user_id={user_id}, type={type_}, deleted={deleted}")
            return deleted or 0
            
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"批量删除消息失败: {e}")
            raise e

    async def mark_multiple_as_read(
        self, 
        user_id: int, 
        message_ids: List[int]
    ) -> Dict[str, Any]:
        """批量标记多个消息为已读（增强版）
        
        Args:
            user_id: 用户ID
            message_ids: 消息ID列表
            
        Returns:
            Dict[str, Any]: 包含操作结果的详细信息
                - success_count: 成功标记的消息数量
                - failed_count: 失败的消息数量
                - failed_message_ids: 失败的消息ID列表
                - total_count: 总消息数量
        """
        start_time = time.time()
        
        if not message_ids:
            return {
                "success_count": 0,
                "failed_count": 0,
                "failed_message_ids": [],
                "total_count": 0
            }
        
        # 使用Redis管道优化批量操作
        pipe = self.redis.pipeline()
        
        # 使用事务确保数据一致性
        transaction = self.db.begin()
        try:
            current_time = datetime.utcnow()
            
            # 查询需要更新的消息接收者记录
            recipients_to_update = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id,
                MessageRecipient.message_id.in_(message_ids),
                MessageRecipient.is_read == False
            ).all()
            
            success_message_ids = [r.message_id for r in recipients_to_update]
            failed_message_ids = list(set(message_ids) - set(success_message_ids))
            
            if recipients_to_update:
                # 批量更新MessageRecipient表
                updated_recipients = self.db.query(MessageRecipient).filter(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.message_id.in_(success_message_ids),
                    MessageRecipient.is_read == False
                ).update(
                    {
                        'is_read': True,
                        'read_at': current_time
                    },
                    synchronize_session=False
                )
            
            # 提交事务
            transaction.commit()
            
            # 异步更新Redis缓存
            try:
                if success_message_ids:
                    await self._update_cache_after_read_batch(user_id, success_message_ids, pipe)
                    pipe.execute()
            except Exception as cache_error:
                logger.warning(f"批量缓存更新失败，但数据库操作成功 - 用户:{user_id}, 错误:{cache_error}")
            
            result = {
                "success_count": len(success_message_ids),
                "failed_count": len(failed_message_ids),
                "failed_message_ids": failed_message_ids,
                "total_count": len(message_ids)
            }
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("mark_multiple_as_read", duration, {
                "user_id": user_id,
                "total_messages": len(message_ids),
                "success_count": result["success_count"],
                "failed_count": result["failed_count"],
                "success": True
            })
            
            logger.info(f"批量标记消息已读完成 - 用户:{user_id}, 总数:{len(message_ids)}, 成功:{result['success_count']}, 失败:{result['failed_count']}, 耗时:{duration:.3f}s")
            
            return result
            
        except Exception as e:
            transaction.rollback()
            duration = time.time() - start_time
            
            # 记录错误性能指标
            self._log_performance("mark_multiple_as_read", duration, {
                "user_id": user_id,
                "total_messages": len(message_ids),
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"批量标记消息已读失败 - 用户:{user_id}, 消息数:{len(message_ids)}, 耗时:{duration:.3f}s, 错误:{e}")
            raise e

    async def get_read_status(
        self, 
        user_id: int, 
        message_id: int
    ) -> Dict[str, Any]:
        """获取单个消息的已读状态
        
        Args:
            user_id: 用户ID
            message_id: 消息ID
            
        Returns:
            Dict[str, Any]: 消息状态信息
                - is_read: 是否已读
                - read_at: 已读时间（如果已读）
                - message_exists: 消息是否存在
                - is_recipient: 用户是否为接收者
        """
        start_time = time.time()
        
        try:
            # 先尝试从Redis缓存获取
            cache_key = f"message_read_status:{user_id}:{message_id}"
            cached_status = self.redis.get(cache_key)
            
            if cached_status:
                result = json.loads(cached_status)
                duration = time.time() - start_time
                self._log_cache_metrics("get_read_status", cache_key, True, len(cached_status), duration)
                return result
            
            # 从数据库查询
            recipient = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id,
                MessageRecipient.message_id == message_id
            ).first()
            
            # 检查消息是否存在
            message_exists = self.db.query(Message).filter(Message.id == message_id).first() is not None
            
            result = {
                "is_read": recipient.is_read if recipient else False,
                "read_at": recipient.read_at.isoformat() if recipient and recipient.read_at else None,
                "message_exists": message_exists,
                "is_recipient": recipient is not None
            }
            
            # 缓存结果（5分钟过期）
            try:
                self.redis.setex(cache_key, 300, json.dumps(result, default=str))
            except Exception as cache_error:
                logger.warning(f"缓存读取状态失败: {cache_error}")
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("get_read_status", duration, {
                "user_id": user_id,
                "message_id": message_id,
                "is_read": result["is_read"],
                "success": True
            })
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_performance("get_read_status", duration, {
                "user_id": user_id,
                "message_id": message_id,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"获取消息读取状态失败 - 用户:{user_id}, 消息:{message_id}, 错误:{e}")
            raise e

    async def get_message_read_statistics(
        self, 
        message_id: int
    ) -> Dict[str, Any]:
        """获取消息的阅读统计信息
        
        Args:
            message_id: 消息ID
            
        Returns:
            Dict[str, Any]: 阅读统计信息
                - total_recipients: 总接收者数量
                - read_count: 已读数量
                - unread_count: 未读数量
                - read_rate: 已读率（百分比）
                - read_details: 已读用户详情列表
        """
        start_time = time.time()
        
        try:
            # 先尝试从Redis缓存获取
            cache_key = f"message_read_stats:{message_id}"
            cached_stats = self.redis.get(cache_key)
            
            if cached_stats:
                result = json.loads(cached_stats)
                duration = time.time() - start_time
                self._log_cache_metrics("get_message_read_statistics", cache_key, True, len(cached_stats), duration)
                return result
            
            # 从数据库查询统计信息
            recipients = self.db.query(MessageRecipient).filter(
                MessageRecipient.message_id == message_id
            ).all()
            
            if not recipients:
                result = {
                    "total_recipients": 0,
                    "read_count": 0,
                    "unread_count": 0,
                    "read_rate": 0.0,
                    "read_details": []
                }
            else:
                read_recipients = [r for r in recipients if r.is_read]
                unread_recipients = [r for r in recipients if not r.is_read]
                
                # 获取已读用户的详细信息
                read_details = []
                for recipient in read_recipients:
                    # 这里可以根据需要添加用户信息查询
                    read_details.append({
                        "user_id": recipient.recipient_id,
                        "read_at": recipient.read_at.isoformat() if recipient.read_at else None
                    })
                
                result = {
                    "total_recipients": len(recipients),
                    "read_count": len(read_recipients),
                    "unread_count": len(unread_recipients),
                    "read_rate": round((len(read_recipients) / len(recipients)) * 100, 2),
                    "read_details": read_details
                }
            
            # 缓存结果（10分钟过期）
            try:
                self.redis.setex(cache_key, 600, json.dumps(result, default=str))
            except Exception as cache_error:
                logger.warning(f"缓存消息统计失败: {cache_error}")
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("get_message_read_statistics", duration, {
                "message_id": message_id,
                "total_recipients": result["total_recipients"],
                "read_count": result["read_count"],
                "success": True
            })
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_performance("get_message_read_statistics", duration, {
                "message_id": message_id,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"获取消息阅读统计失败 - 消息:{message_id}, 错误:{e}")
            raise e

    async def _update_cache_after_read_batch(
        self, 
        user_id: int, 
        message_ids: List[int], 
        pipe
    ) -> None:
        """批量更新缓存（使用Redis管道优化）
        
        Args:
            user_id: 用户ID
            message_ids: 消息ID列表
            pipe: Redis管道对象
        """
        try:
            # 清理相关的消息列表缓存
            cache_patterns = [
                f"messages:user:{user_id}:*",
                f"recent_messages:{user_id}:*",
                f"message_stats:{user_id}"
            ]
            
            for pattern in cache_patterns:
                keys = self.redis.keys(pattern)
                if keys:
                    pipe.delete(*keys)
            
            # 更新未读消息数量
            unread_key = f"unread_count:{user_id}"
            current_unread = self.redis.get(unread_key)
            if current_unread:
                new_unread = max(0, int(current_unread) - len(message_ids))
                pipe.set(unread_key, new_unread)
            
            # 清理单个消息的读取状态缓存
            for message_id in message_ids:
                status_key = f"message_read_status:{user_id}:{message_id}"
                stats_key = f"message_read_stats:{message_id}"
                pipe.delete(status_key, stats_key)
            
            logger.debug(f"批量缓存更新准备完成 - 用户:{user_id}, 消息数:{len(message_ids)}")
             
        except Exception as e:
             logger.error(f"批量缓存更新失败 - 用户:{user_id}, 错误:{e}")
             raise e

    async def sync_cache_with_database(
        self, 
        user_id: int, 
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """同步Redis缓存与数据库数据
        
        Args:
            user_id: 用户ID
            force_refresh: 是否强制刷新所有缓存
            
        Returns:
            Dict[str, Any]: 同步结果统计
        """
        start_time = time.time()
        
        try:
            sync_stats = {
                "cache_cleared": 0,
                "cache_updated": 0,
                "inconsistencies_found": 0,
                "errors": []
            }
            
            # 如果强制刷新，清除所有相关缓存
            if force_refresh:
                cache_patterns = [
                    f"messages:user:{user_id}:*",
                    f"recent_messages:{user_id}:*",
                    f"message_stats:{user_id}",
                    f"unread_count:{user_id}",
                    f"message_read_status:{user_id}:*"
                ]
                
                for pattern in cache_patterns:
                    keys = self.redis.keys(pattern)
                    if keys:
                        self.redis.delete(*keys)
                        sync_stats["cache_cleared"] += len(keys)
            
            # 重新计算并缓存未读消息数量
            actual_unread_count = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id,
                MessageRecipient.is_read == False
            ).count()
            
            unread_key = f"unread_count:{user_id}"
            cached_unread = self.redis.get(unread_key)
            
            if not cached_unread or int(cached_unread) != actual_unread_count:
                if cached_unread:
                    sync_stats["inconsistencies_found"] += 1
                self.redis.set(unread_key, actual_unread_count)
                sync_stats["cache_updated"] += 1
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("sync_cache_with_database", duration, {
                "user_id": user_id,
                "force_refresh": force_refresh,
                "cache_cleared": sync_stats["cache_cleared"],
                "cache_updated": sync_stats["cache_updated"],
                "inconsistencies_found": sync_stats["inconsistencies_found"],
                "success": True
            })
            
            logger.info(f"缓存同步完成 - 用户:{user_id}, 清理:{sync_stats['cache_cleared']}, 更新:{sync_stats['cache_updated']}, 不一致:{sync_stats['inconsistencies_found']}, 耗时:{duration:.3f}s")
            
            return sync_stats
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_performance("sync_cache_with_database", duration, {
                "user_id": user_id,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"缓存同步失败 - 用户:{user_id}, 错误:{e}")
            raise e

    async def repair_data_consistency(
        self, 
        user_id: Optional[int] = None,
        message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """修复数据一致性问题
        
        Args:
            user_id: 用户ID（可选，如果提供则只修复该用户的数据）
            message_id: 消息ID（可选，如果提供则只修复该消息的数据）
            
        Returns:
            Dict[str, Any]: 修复结果统计
        """
        start_time = time.time()
        
        try:
            repair_stats = {
                "users_processed": 0,
                "messages_processed": 0,
                "inconsistencies_fixed": 0,
                "cache_entries_updated": 0,
                "errors": []
            }
            
            # 构建查询条件
            query = self.db.query(MessageRecipient)
            if user_id:
                query = query.filter(MessageRecipient.recipient_id == user_id)
            if message_id:
                query = query.filter(MessageRecipient.message_id == message_id)
            
            # 获取需要检查的记录
            recipients = query.all()
            
            # 按用户分组处理
            user_groups = {}
            for recipient in recipients:
                if recipient.recipient_id not in user_groups:
                    user_groups[recipient.recipient_id] = []
                user_groups[recipient.recipient_id].append(recipient)
            
            # 逐用户修复数据
            for uid, user_recipients in user_groups.items():
                try:
                    # 重新计算未读数量
                    actual_unread = sum(1 for r in user_recipients if not r.is_read)
                    unread_key = f"unread_count:{uid}"
                    cached_unread = self.redis.get(unread_key)
                    
                    if not cached_unread or int(cached_unread) != actual_unread:
                        self.redis.set(unread_key, actual_unread)
                        repair_stats["inconsistencies_fixed"] += 1
                        repair_stats["cache_entries_updated"] += 1
                    
                    # 清理可能不一致的缓存
                    cache_patterns = [
                        f"messages:user:{uid}:*",
                        f"recent_messages:{uid}:*",
                        f"message_stats:{uid}"
                    ]
                    
                    for pattern in cache_patterns:
                        keys = self.redis.keys(pattern)
                        if keys:
                            self.redis.delete(*keys)
                            repair_stats["cache_entries_updated"] += len(keys)
                    
                    repair_stats["users_processed"] += 1
                    
                except Exception as user_error:
                    error_msg = f"修复用户 {uid} 数据失败: {user_error}"
                    repair_stats["errors"].append(error_msg)
                    logger.warning(error_msg)
            
            # 处理消息级别的统计缓存
            if message_id:
                try:
                    stats_key = f"message_read_stats:{message_id}"
                    self.redis.delete(stats_key)
                    repair_stats["cache_entries_updated"] += 1
                    repair_stats["messages_processed"] += 1
                except Exception as msg_error:
                    error_msg = f"修复消息 {message_id} 统计失败: {msg_error}"
                    repair_stats["errors"].append(error_msg)
                    logger.warning(error_msg)
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("repair_data_consistency", duration, {
                "user_id": user_id,
                "message_id": message_id,
                "users_processed": repair_stats["users_processed"],
                "messages_processed": repair_stats["messages_processed"],
                "inconsistencies_fixed": repair_stats["inconsistencies_fixed"],
                "success": len(repair_stats["errors"]) == 0
            })
            
            logger.info(f"数据一致性修复完成 - 用户:{repair_stats['users_processed']}, 消息:{repair_stats['messages_processed']}, 修复:{repair_stats['inconsistencies_fixed']}, 错误:{len(repair_stats['errors'])}, 耗时:{duration:.3f}s")
            
            return repair_stats
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_performance("repair_data_consistency", duration, {
                "user_id": user_id,
                "message_id": message_id,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"数据一致性修复失败 - 错误:{e}")
            raise e

    async def validate_cache_consistency(
        self, 
        user_id: int,
        sample_size: int = 10
    ) -> Dict[str, Any]:
        """验证缓存一致性
        
        Args:
            user_id: 用户ID
            sample_size: 抽样验证的消息数量
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        start_time = time.time()
        
        try:
            validation_result = {
                "is_consistent": True,
                "unread_count_consistent": True,
                "sample_messages_consistent": True,
                "inconsistencies": [],
                "recommendations": []
            }
            
            # 验证未读消息数量
            actual_unread = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id,
                MessageRecipient.is_read == False
            ).count()
            
            unread_key = f"unread_count:{user_id}"
            cached_unread = self.redis.get(unread_key)
            
            if not cached_unread or int(cached_unread) != actual_unread:
                validation_result["is_consistent"] = False
                validation_result["unread_count_consistent"] = False
                validation_result["inconsistencies"].append({
                    "type": "unread_count_mismatch",
                    "cached_value": int(cached_unread) if cached_unread else None,
                    "actual_value": actual_unread
                })
                validation_result["recommendations"].append("执行缓存同步修复未读数量")
            
            # 抽样验证消息状态
            sample_recipients = self.db.query(MessageRecipient).filter(
                MessageRecipient.recipient_id == user_id
            ).limit(sample_size).all()
            
            for recipient in sample_recipients:
                cache_key = f"message_read_status:{user_id}:{recipient.message_id}"
                cached_status = self.redis.get(cache_key)
                
                if cached_status:
                    try:
                        cached_data = json.loads(cached_status)
                        if cached_data.get("is_read") != recipient.is_read:
                            validation_result["is_consistent"] = False
                            validation_result["sample_messages_consistent"] = False
                            validation_result["inconsistencies"].append({
                                "type": "message_status_mismatch",
                                "message_id": recipient.message_id,
                                "cached_status": cached_data.get("is_read"),
                                "actual_status": recipient.is_read
                            })
                    except json.JSONDecodeError:
                        validation_result["inconsistencies"].append({
                            "type": "invalid_cache_data",
                            "message_id": recipient.message_id,
                            "cache_key": cache_key
                        })
            
            if validation_result["inconsistencies"]:
                validation_result["recommendations"].append("执行数据一致性修复")
            
            # 记录性能指标
            duration = time.time() - start_time
            self._log_performance("validate_cache_consistency", duration, {
                "user_id": user_id,
                "sample_size": sample_size,
                "is_consistent": validation_result["is_consistent"],
                "inconsistencies_count": len(validation_result["inconsistencies"]),
                "success": True
            })
            
            return validation_result
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_performance("validate_cache_consistency", duration, {
                "user_id": user_id,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"缓存一致性验证失败 - 用户:{user_id}, 错误:{e}")
            raise e