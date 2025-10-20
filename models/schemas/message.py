from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class WebSocketMessage(BaseModel):
    type: str  # "audio_chunk", "text_message", "transcription"
    meeting_id: str
    speaker_id: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded audio
    text: Optional[str] = None
    timestamp: Optional[datetime] = None