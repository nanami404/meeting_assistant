# 标准库
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

# 第三方库
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# 自定义类
from .service_models import Meeting, Participant, Transcription, PersonSign, User
from schemas import MeetingCreate,TranscriptionCreate, PersonSignCreate


class MeetingService(object):
    async def create_meeting(self, db: Session, meeting_data: MeetingCreate) -> Meeting:
        """Create a new meeting with participants"""
        # Create meeting
        meeting = Meeting(
            id=str(uuid.uuid4()),
            title=meeting_data.title,
            description=meeting_data.description,
            date_time=meeting_data.date_time,
            location=meeting_data.location,
            duration_minutes=meeting_data.duration_minutes,
            agenda=meeting_data.agenda,
            status="scheduled"
        )
        db.add(meeting)
        # Get the meeting ID
        db.flush()
        # Create participants
        for participant_data in meeting_data.participants:
            participant = Participant(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                name=participant_data.name,
                email=participant_data.email,
                role=participant_data.role,
                is_required=participant_data.is_required
            )
            db.add(participant)
        db.commit()
        db.refresh(meeting)
        return meeting

    async def get_meetings(self, db: Session) -> list[Meeting]:
        """Get all meetings"""
        return db.query(Meeting).order_by(Meeting.date_time.desc()).all()

    async def get_meeting(self, db: Session, meeting_id: str) -> Optional[Meeting]:
        """Get a specific meeting by ID"""
        return db.query(Meeting).filter(Meeting.id == meeting_id).first()

    async def update_meeting(self, db: Session, meeting_id: str, meeting_data: MeetingCreate) -> Optional[Meeting]:
        """Update a meeting"""
        from time import timezone
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return None
        # Update meeting fields
        meeting.title = meeting_data.title
        meeting.description = meeting_data.description
        meeting.date_time = meeting_data.date_time
        meeting.location = meeting_data.location
        meeting.duration_minutes = meeting_data.duration_minutes
        meeting.agenda = meeting_data.agenda
        #meeting.updated_at = datetime.now(timezone.utc)  #
        meeting.updated_at = datetime.utcnow()
        # Update participants - remove existing and add new ones
        db.query(Participant).filter(Participant.meeting_id == meeting_id).delete()
        for participant_data in meeting_data.participants:
            participant = Participant(
                id=str(uuid.uuid4()),
                meeting_id=meeting.id,
                name=participant_data.name,
                email=participant_data.email,
                role=participant_data.role,
                is_required=participant_data.is_required
            )
            db.add(participant)
        db.commit()
        db.refresh(meeting)
        return meeting

    async def delete_meeting(self, db: Session, meeting_id: str) -> bool:
        """Delete a meeting"""
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return False

        db.delete(meeting)
        db.commit()
        return True

    async def get_people_sign_status(self, db: Session) -> List[PersonSign]:
        """查询所有人员的签到状态（从数据库）"""
        # 可添加排序、过滤等逻辑（如按姓名排序）
        return db.query(PersonSign).order_by(PersonSign.name).all()

    async def sign_person(self, db: Session, name: str, meeting_id: str,user_id: str) -> Dict[str, str]:
        """
        处理人员签到逻辑（绑定会议维度，确保签到状态仅对当前会议生效）
        :param db: 数据库会话
        :param name: 人员姓名
        :param meeting_id: 会议ID（字符串类型，适配原参数）
        :return: 签到结果消息
        """
        # 1. 验证会议存在性（会议不存在直接抛404，而非返回None）
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )

        # 2. 验证人员存在性（人员不存在抛404，而非仅打印日志）
        person = db.query(Participant).filter(Participant.name == name, Participant.meeting_id == meeting_id).first()
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 未找到人员 {name}"
            )

        # 3. 查找“人员-会议”关联的签到记录（核心：绑定会议维度，避免全局状态污染）
        # 注意：此处需用数据库模型 PersonSign，而非 Pydantic 模型 PersonSignCreate
        user_meeting_sign = db.query(PersonSign).filter(
            PersonSign.name == name,
            PersonSign.meeting_id == meeting_id
        ).first()

        # 4. 无关联记录则创建（用数据库模型实例，而非Pydantic实例）
        if not user_meeting_sign:
            # 错误修正：创建 PersonSign（数据库模型）实例，而非 PersonSignCreate（Pydantic模型）
            user_meeting_sign = PersonSign(
                name=name,
                user_code=user_id,
                meeting_id=meeting_id,
                is_signed=False,  # 初始未签到
                is_on_leave=False  # 初始未请假
            )
            db.add(user_meeting_sign)  # 数据库模型可正常添加

        # 5. 更新当前会议的签到状态（仅修改“人员-会议”关联记录，而非全局人员状态）
        # 错误修正：原代码修改 person（全局状态），现改为修改 user_meeting_sign（会议维度状态）
        user_meeting_sign.is_signed = True
        user_meeting_sign.is_on_leave = False

        # 6. 提交事务并刷新（确保获取最新数据库状态）
        try:
            db.commit()
            db.refresh(user_meeting_sign)  # 刷新关联记录实例，而非全局person实例
        except Exception as e:
            db.rollback()  # 事务失败回滚，避免数据异常
            raise HTTPException(
                status_code=500,
                detail=f"签到事务提交失败：{str(e)}"
            )

        # 7. 返回带会议信息的明确消息（提升用户体验）
        return {
            "message": f"{name} 在会议【{meeting.title}】（ID：{meeting_id}）中签到成功",
            "meeting_id": meeting_id,
            "is_signed": user_meeting_sign.is_signed
        }

    async def leave_person(self, db: Session, name: str, meeting_id: str, user_id:int) -> Dict[str, str]:
        """
        处理指定会议的人员请假逻辑
        :param db: 数据库会话
        :param name: 人员姓名
        :param meeting_id: 会议ID（限制请假仅对当前会议有效）
        :return: 请假结果消息
        """
        # 1. 验证会议是否存在
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 不存在"
            )

        # 2. 验证人员是否存在
        person = db.query(Participant).filter(Participant.name == name, Participant.meeting_id == meeting_id).first()
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"会议 ID {meeting_id} 未找到人员 {name}"
            )

        # 3. 查找该人员在当前会议中的关联记录（无记录则自动创建）
        user_meeting = db.query(PersonSign).filter(
            PersonSign.name == name,
            PersonSign.meeting_id == meeting_id
        ).first()

        if not user_meeting:
            # 自动创建“人员-会议”关联记录（默认未请假状态）
            user_meeting = PersonSign(
                name=name,
                meeting_id=meeting_id,
                user_code=user_id,
                is_signed=False,
                is_on_leave=False
            )
            db.add(user_meeting)

        # 4. 更新请假状态（仅对当前会议生效，同时取消签到状态）
        user_meeting.is_on_leave = True
        user_meeting.is_signed = False

        # 5. 提交事务（带回滚机制）
        try:
            db.commit()
            db.refresh(user_meeting)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"请假事务提交失败: {str(e)}"
            )

        # 6. 返回包含会议信息的结果
        return {
            "message": f"{name} 在会议【{meeting.title}】（ID：{meeting_id}）中请假成功",
            "meeting_id": meeting_id,
            "is_on_leave": user_meeting.is_on_leave
        }

    async def save_transcription(self, db: AsyncSession, transcription_data: TranscriptionCreate) -> Transcription:
        # 新增：查询会议是否存在（异步操作，必须加 await）
        # 关键：await 不可少
        from time import timezone
        meeting_result = await db.execute(
            select(Meeting).filter(Meeting.id == transcription_data.meeting_id)
        )
        meeting = meeting_result.scalars().first()
        if not meeting:
            raise ValueError(f"会议 {transcription_data.meeting_id} 不存在")
        # 验证必填字段（不变）
        if not all([transcription_data.meeting_id, transcription_data.speaker_id, transcription_data.text]):
            raise ValueError("meeting_id, speaker_id和text是必填字段")

        try:
            # 关键修复：用 async with 开启异步事务，自动管理提交/回滚
            transcription = Transcription(
                id=str(uuid.uuid4()),
                meeting_id=transcription_data.meeting_id,
                speaker_id=transcription_data.speaker_id,
                speaker_name=transcription_data.speaker_name,
                text=transcription_data.text,
                timestamp=transcription_data.timestamp or datetime.now(timezone.utc),
                confidence_score=transcription_data.confidence_score
            )
            # add 是同步方法，无需 await
            db.add(transcription)
            await db.commit()
            # 事务提交后，异步刷新对象（已加 await，正确）
            await db.refresh(transcription)

            return transcription

        except Exception as e:
            # 记录错误日志（建议用 logging 模块，而非 print）
            import logging
            logging.error(f"保存转录记录失败: {str(e)}")
            # 注：若用了 async with db.begin()，异常会自动回滚，无需手动 await db.rollback()
            # 重新抛出异常，让接口层捕获并返回 500 错误
            raise e

    async def get_meeting_transcriptions(self, db: Session, meeting_id: str) -> list[Transcription]:
        """Get all transcriptions for a meeting"""
        return db.query(Transcription).filter(Transcription.meeting_id == meeting_id).order_by(
            Transcription.timestamp.asc()).all()

    async def update_meeting_status(self, db: Session, meeting_id: str, status: str) -> bool:
        """Update meeting status"""
        from time import timezone
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return False

        meeting.status = status
        meeting.updated_at = datetime.now(timezone.utc) # Compliant

        db.commit()
        return True

    async def mark_action_items(self, db: Session, transcription_ids: list[str]) -> bool:
        """Mark transcriptions as action items"""
        transcriptions = db.query(Transcription).filter(
            Transcription.id.in_(transcription_ids)
        ).all()

        for transcription in transcriptions:
            transcription.is_action_item = True

        db.commit()
        return True

    async def mark_decisions(self, db: Session, transcription_ids: list[str]) -> bool:
        """Mark transcriptions as decisions"""
        transcriptions = db.query(Transcription).filter(
            Transcription.id.in_(transcription_ids)
        ).all()
        for transcription in transcriptions:
            transcription.is_decision = True
        db.commit()
        return True
