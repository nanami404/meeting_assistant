# 标准库
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from loguru import logger

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

# 自定义模块
from models.database import Message, MessageRecipient, User, UserRole
from models.schemas import MessageCreate, MessageUpdate, MessageRecipientUpdate
from services.user_service import UserService


class MessageService(object):
    """消息业务逻辑层
    提供消息的增删改查与状态管理功能。
    """

    def __init__(self):
        self.user_service = UserService()

    async def create_message(self, db: Session, current_user_id: int, message_data: MessageCreate) -> Message:
        """创建新消息（仅管理员可发送）
        
        Args:
            db: 数据库会话
            current_user_id: 当前用户ID
            message_data: 消息创建数据
            
        Returns:
            Message: 创建的消息对象
            
        Raises:
            ValueError: 当用户不是管理员或参数错误时
            Exception: 其他数据库操作异常
        """
        try:
            # 验证用户为管理员
            user = await self.user_service.get_user_by_id(db, current_user_id)
            if not user:
                logger.warning(f"用户不存在: user_id={current_user_id}")
                raise ValueError("用户不存在")
                
            if user.user_role != UserRole.ADMIN.value:
                logger.warning(f"非管理员用户尝试发送消息: user_id={current_user_id}, role={user.user_role}")
                raise ValueError("只有管理员可以发送消息")

            # 验证输入参数
            if not message_data.title and not message_data.content:
                logger.warning("消息标题和内容不能同时为空")
                raise ValueError("消息标题和内容不能同时为空")
                
            if not message_data.recipient_ids:
                logger.warning("消息接收者列表不能为空")
                raise ValueError("消息接收者列表不能为空")

            # 开始事务
            db.begin()

            # 创建消息记录
            message = Message(
                title=message_data.title,
                content=message_data.content,
                sender_id=current_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(message)
            db.flush()  # 获取message.id

            # 为每个recipient_id创建关联记录
            valid_recipient_count = 0
            invalid_recipients = []
            for recipient_id in message_data.recipient_ids:
                # 验证接收者是否存在
                recipient_user = await self.user_service.get_user_by_id(db, recipient_id)
                if recipient_user:
                    message_recipient = MessageRecipient(
                        message_id=message.id,
                        recipient_id=recipient_id,
                        is_read=False,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(message_recipient)
                    valid_recipient_count += 1
                else:
                    invalid_recipients.append(recipient_id)
                    logger.warning(f"消息接收者不存在，已跳过: recipient_id={recipient_id}")

            # 如果没有有效的接收者，回滚事务
            if valid_recipient_count == 0:
                db.rollback()
                logger.warning(f"没有有效的消息接收者: invalid_recipients={invalid_recipients}")
                raise ValueError("没有有效的消息接收者")

            db.commit()
            db.refresh(message)
            logger.info(f"管理员 {current_user_id} 成功发送消息: {message.id} 给 {valid_recipient_count} 个用户, 无效接收者: {len(invalid_recipients)} 个")
            return message

        except ValueError as ve:
            logger.warning(f"创建消息参数错误: {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"创建消息失败: {e}")
            db.rollback()
            raise e

    async def get_user_messages(
        self,
        db: Session,
        current_user_id: int,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None
    ) -> Tuple[List[MessageRecipient], int]:
        """查询当前用户的消息接收记录
        
        Args:
            db: 数据库会话
            current_user_id: 当前用户ID
            page: 页码，默认为1
            page_size: 每页大小，默认为20
            is_read: 已读状态过滤，None表示不过滤
            
        Returns:
            tuple: (消息接收记录列表, 总数)
        """
        try:
            # 验证参数
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 20
                
            # 构建查询
            query = db.query(MessageRecipient).join(Message).filter(
                MessageRecipient.recipient_id == current_user_id
            )

            # 应用已读状态过滤
            if is_read is not None:
                query = query.filter(MessageRecipient.is_read == is_read)

            # 获取总数
            total = query.count()

            # 应用分页和排序（按创建时间倒序）
            page = max(1, page)
            page_size = max(1, min(page_size, 100))  # 限制最大100
            offset = (page - 1) * page_size
            items = query.order_by(MessageRecipient.created_at.desc()).offset(offset).limit(page_size).all()

            logger.info(f"用户 {current_user_id} 查询消息列表: 页码={page}, 页大小={page_size}, 总数={total}, 已读过滤={is_read}")
            return items, total

        except Exception as e:
            logger.error(f"查询用户消息列表失败: {e}")
            raise e

    async def mark_messages_as_read(
        self,
        db: Session,
        current_user_id: int,
        message_id: Optional[int] = None,
        mark_all: bool = False
    ) -> int:
        """标记消息为已读
        
        Args:
            db: 数据库会话
            current_user_id: 当前用户ID
            message_id: 消息ID（标记单条消息）
            mark_all: 是否标记所有未读消息为已读
            
        Returns:
            int: 更新的记录数量
        """
        try:
            # 验证参数
            if message_id is not None and message_id <= 0:
                logger.warning(f"无效的消息ID: message_id={message_id}")
                raise ValueError("无效的消息ID")
                
            # 开始事务
            db.begin()

            # 构建更新条件
            update_conditions = [MessageRecipient.recipient_id == current_user_id]
            
            # 如果不是标记所有，则添加已读状态过滤
            if not mark_all:
                update_conditions.append(MessageRecipient.is_read == False)
            
            # 如果指定了消息ID，则添加消息ID过滤
            if message_id is not None:
                # 验证用户是否有权限操作该消息
                msg_recipient = db.query(MessageRecipient).filter(
                    and_(
                        MessageRecipient.message_id == message_id,
                        MessageRecipient.recipient_id == current_user_id
                    )
                ).first()
                
                if not msg_recipient:
                    db.rollback()
                    logger.warning(f"用户尝试标记非自己接收的消息: user_id={current_user_id}, message_id={message_id}")
                    raise ValueError("无权限操作该消息")
                    
                update_conditions.append(MessageRecipient.message_id == message_id)

            # 执行更新
            current_time = datetime.now(timezone.utc)
            updated_count = db.query(MessageRecipient).filter(
                and_(*update_conditions)
            ).update({
                MessageRecipient.is_read: True,
                MessageRecipient.read_at: current_time
            }, synchronize_session=False)

            db.commit()
            action = "标记所有未读消息" if mark_all else f"标记消息 {message_id}"
            logger.info(f"用户 {current_user_id} {action} 为已读，更新数量: {updated_count}")
            return updated_count

        except ValueError as ve:
            logger.warning(f"标记消息为已读参数错误: {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"标记消息为已读失败: {e}")
            db.rollback()
            raise e

    async def delete_messages(
        self,
        db: Session,
        current_user_id: int,
        message_id: Optional[int] = None,
        delete_type: Optional[str] = None
    ) -> int:
        """删除消息
        
        Args:
            db: 数据库会话
            current_user_id: 当前用户ID
            message_id: 消息ID（删除单条消息）
            delete_type: 删除类型（"all"-全部, "read"-已读, "unread"-未读）
            
        Returns:
            int: 删除的记录数量
        """
        try:
            # 验证参数
            if message_id is not None and message_id <= 0:
                logger.warning(f"无效的消息ID: message_id={message_id}")
                raise ValueError("无效的消息ID")
                
            if delete_type and delete_type not in ["read", "unread", "all"]:
                logger.warning(f"无效的删除类型: delete_type={delete_type}")
                raise ValueError("无效的删除类型")
                
            # 开始事务
            db.begin()

            # 构建删除条件
            delete_conditions = [MessageRecipient.recipient_id == current_user_id]

            # 根据参数确定删除条件
            if message_id is not None:
                # 验证用户是否有权限删除该消息
                msg_recipient = db.query(MessageRecipient).filter(
                    and_(
                        MessageRecipient.message_id == message_id,
                        MessageRecipient.recipient_id == current_user_id
                    )
                ).first()
                
                if not msg_recipient:
                    db.rollback()
                    logger.warning(f"用户尝试删除非自己接收的消息: user_id={current_user_id}, message_id={message_id}")
                    raise ValueError("无权限删除该消息")
                    
                delete_conditions.append(MessageRecipient.message_id == message_id)
            elif delete_type == "read":
                # 删除已读消息
                delete_conditions.append(MessageRecipient.is_read == True)
            elif delete_type == "unread":
                # 删除未读消息
                delete_conditions.append(MessageRecipient.is_read == False)
            elif delete_type == "all":
                # 删除所有消息（条件已包含recipient_id）
                pass
            else:
                # 如果没有指定message_id且delete_type为None，则不执行删除
                db.rollback()
                logger.warning("删除消息参数不完整")
                return 0

            # 执行删除
            deleted_count = db.query(MessageRecipient).filter(
                and_(*delete_conditions)
            ).delete(synchronize_session=False)

            db.commit()
            action = f"删除消息 {message_id}" if message_id else f"按类型删除消息 {delete_type}"
            logger.info(f"用户 {current_user_id} {action}，删除数量: {deleted_count}")
            return deleted_count

        except ValueError as ve:
            logger.warning(f"删除消息参数错误: {ve}")
            db.rollback()
            raise ve
        except Exception as e:
            logger.error(f"删除消息失败: {e}")
            db.rollback()
            raise e