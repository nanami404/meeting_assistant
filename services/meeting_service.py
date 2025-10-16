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
