# 标准库
from datetime import datetime
from typing import List, Optional, Tuple

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
        
        # WebSocket 连接管理器（延迟导入避免循环依赖）
        self._ws_manager = None

    async def send_message(
        self,
        db: Session,
        sender_id: int,
        recipient_ids: List[int],
        title: str,
        content: str,
        message_type: str = "system"
    ) -> Message:
        """发送消息给多个接收者
        
        Args:
            db: 数据库会话
            sender_id: 发送者ID
            recipient_ids: 接收者ID列表
            title: 消息标题
            content: 消息内容
            message_type: 消息类型
            
        Returns:
            Message: 创建的消息对象
            
        Raises:
            ValueError: 接收者列表为空时抛出
            Exception: 发送失败时抛出异常
        """
        if not recipient_ids:
            raise ValueError("接收者列表不能为空")
        
        # 去重接收者ID
        unique_recipient_ids = list(set(recipient_ids))
        
        try:
            # 1. 创建主消息记录
            msg = Message(
                sender_id=sender_id,
                title=title,
                content=content,
                message_type=message_type,
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
            
            logger.info(f"消息发送成功 id={msg.id} sender={sender_id} -> recipients={unique_recipient_ids}")
            
            # 3. 更新Redis缓存
            await self._update_cache_after_send(unique_recipient_ids)
            
            # 4. 实时推送给在线接收者
            await self._push_new_message_to_online_users(msg, unique_recipient_ids)
            
            return msg
            
        except Exception as e:
            db.rollback()
            logger.error(f"消息发送失败: {e}")
            raise e

    async def list_messages(
        self,
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
        message_type: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """查询用户消息列表
        
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
        try:
            # 构建查询
            query = db.query(MessageRecipient).join(
                Message, MessageRecipient.message_id == Message.id
            ).filter(MessageRecipient.recipient_id == user_id)
            
            # 添加过滤条件
            if is_read is not None:
                query = query.filter(MessageRecipient.is_read == is_read)
            if message_type:
                query = query.filter(Message.message_type == message_type)

            # 获取总数
            total = query.count()
            
            # 分页查询
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 20
            if page_size > 100:
                page_size = 100

            offset = (page - 1) * page_size
            message_recipients = query.options(
                joinedload(MessageRecipient.message).joinedload(Message.sender)
            ).order_by(
                MessageRecipient.created_at.desc()
            ).offset(offset).limit(page_size).all()

            # 转换为字典格式
            messages_data = []
            for mr in message_recipients:
                msg = mr.message
                msg_dict = {
                    'id': msg.id,
                    'title': msg.title,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'message_type': msg.message_type,
                    'is_read': mr.is_read,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    'sender_name': msg.sender.user_name if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None,
                    'recipient_read_at': mr.read_at.isoformat() if mr.read_at else None
                }
                messages_data.append(msg_dict)

            logger.info(f"查询消息列表成功 - 用户:{user_id}, 页码:{page}, 结果:{len(messages_data)}/{total}")
            return messages_data, total
            
        except Exception as e:
            logger.error(f"查询消息列表失败 - 用户:{user_id}, 错误:{e}")
            raise e

    async def mark_messages_as_read(
        self,
        db: Session,
        user_id: int,
        message_ids: List[int]
    ) -> bool:
        """标记消息为已读
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            message_ids: 消息ID列表
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 更新消息接收者记录
            updated_count = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.message_id.in_(message_ids),
                    MessageRecipient.is_read == False
                )
            ).update(
                {
                    'is_read': True,
                    'read_at': datetime.utcnow()
                },
                synchronize_session=False
            )
            
            db.commit()
            
            if updated_count > 0:
                # 更新缓存
                await self._clear_user_cache(user_id)
                logger.info(f"标记消息已读成功 - 用户:{user_id}, 消息数:{updated_count}")
            
            return updated_count > 0
            
        except Exception as e:
            db.rollback()
            logger.error(f"标记消息已读失败 - 用户:{user_id}, 错误:{e}")
            raise e

    async def delete_messages(
        self,
        db: Session,
        user_id: int,
        message_ids: List[int]
    ) -> bool:
        """删除用户消息（软删除）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            message_ids: 消息ID列表
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 删除消息接收者记录
            deleted_count = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.message_id.in_(message_ids)
                )
            ).delete(synchronize_session=False)
            
            db.commit()
            
            if deleted_count > 0:
                # 更新缓存
                await self._clear_user_cache(user_id)
                logger.info(f"删除消息成功 - 用户:{user_id}, 消息数:{deleted_count}")
            
            return deleted_count > 0
            
        except Exception as e:
            db.rollback()
            logger.error(f"删除消息失败 - 用户:{user_id}, 错误:{e}")
            raise e

    async def get_unread_count(self, db: Session, user_id: int) -> int:
        """获取用户未读消息数量
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            int: 未读消息数量
        """
        try:
            # 尝试从缓存获取
            if self.redis_service:
                cache_key = f"{self.CACHE_PREFIX_UNREAD_COUNT}{user_id}"
                cached_count = await self.redis_service.get(cache_key)
                if cached_count is not None:
                    return int(cached_count)
            
            # 从数据库查询
            count = db.query(MessageRecipient).filter(
                and_(
                    MessageRecipient.recipient_id == user_id,
                    MessageRecipient.is_read == False
                )
            ).count()
            
            # 缓存结果
            if self.redis_service:
                await self.redis_service.set(
                    cache_key, 
                    str(count), 
                    ex=self.CACHE_EXPIRE_TIME
                )
            
            return count
            
        except Exception as e:
            logger.error(f"获取未读消息数量失败 - 用户:{user_id}, 错误:{e}")
            return 0

    async def search_messages(
        self,
        db: Session,
        user_id: int,
        keyword: str,
        message_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[dict], int]:
        """搜索用户消息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            keyword: 搜索关键词
            message_type: 消息类型过滤
            is_read: 是否已读过滤
            page: 页码
            page_size: 每页大小
            
        Returns:
            Tuple[List[dict], int]: 搜索结果和总数
        """
        try:
            # 构建查询
            query = db.query(MessageRecipient).join(Message).filter(
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
                    'sender_name': msg.sender.user_name if msg.sender else None,
                    'sender_email': msg.sender.email if msg.sender else None,
                    'recipient_read_at': mr.read_at.isoformat() if mr.read_at else None
                }
                messages_data.append(msg_dict)
            
            logger.info(f"搜索消息完成 - 用户:{user_id}, 关键词:'{keyword}', 结果:{len(messages_data)}/{total}")
            return messages_data, total
            
        except Exception as e:
            logger.error(f"搜索消息失败 - 用户:{user_id}, 关键词:'{keyword}', 错误:{e}")
            raise e

    # 私有方法 - 缓存管理
    async def _update_cache_after_send(self, recipient_ids: List[int]) -> None:
        """发送消息后更新Redis缓存
        
        Args:
            recipient_ids: 接收者ID列表
        """
        if not self.redis_service:
            return
            
        try:
            # 为每个接收者更新缓存
            for recipient_id in recipient_ids:
                # 清除消息列表缓存
                await self._clear_user_cache(recipient_id)
                
                # 增加未读消息数量
                cache_key_unread = f"{self.CACHE_PREFIX_UNREAD_COUNT}{recipient_id}"
                await self.redis_service.increment(cache_key_unread)
                await self.redis_service.expire(cache_key_unread, self.CACHE_EXPIRE_TIME)
                
            logger.debug(f"消息发送后缓存更新成功，接收者: {recipient_ids}")
            
        except Exception as e:
            logger.warning(f"消息发送后缓存更新失败: {e}")

    async def _clear_user_cache(self, user_id: int) -> None:
        """清除用户相关缓存
        
        Args:
            user_id: 用户ID
        """
        if not self.redis_service:
            return
            
        try:
            # 清除消息列表缓存
            cache_key_messages = f"{self.CACHE_PREFIX_MESSAGES}{user_id}*"
            keys = await self.redis_service.keys(cache_key_messages)
            if keys:
                await self.redis_service.delete(*keys)
            
            # 清除未读消息计数缓存
            cache_key_unread = f"{self.CACHE_PREFIX_UNREAD_COUNT}{user_id}"
            await self.redis_service.delete(cache_key_unread)
            
        except Exception as e:
            logger.warning(f"清除用户缓存失败 - 用户:{user_id}, 错误:{e}")

    async def _push_new_message_to_online_users(self, message: Message, recipient_ids: List[int]) -> None:
        """推送新消息给在线用户
        
        Args:
            message: 消息对象
            recipient_ids: 接收者ID列表
        """
        try:
            # 延迟导入避免循环依赖
            if self._ws_manager is None:
                from ..websocket.messages_manager import message_ws_manager
                self._ws_manager = message_ws_manager
            
            # 构造消息数据
            message_data = {
                'id': message.id,
                'title': message.title,
                'content': message.content,
                'sender_id': message.sender_id,
                'message_type': message.message_type,
                'created_at': message.created_at.isoformat() if message.created_at else None
            }
            
            # 推送给每个在线接收者
            for recipient_id in recipient_ids:
                await self._ws_manager.send_message_to_user(recipient_id, {
                    'type': 'new_message',
                    'data': message_data
                })
            
            logger.debug(f"新消息推送完成 - 消息ID:{message.id}, 接收者:{recipient_ids}")
            
        except Exception as e:
            logger.warning(f"推送新消息失败 - 消息ID:{message.id}, 错误:{e}")