
from .meeting_manage import router as meeting_manage
from .user_manage import router as user_manage
from .message_manage import router as message_manage
from .attendance_manage import router as attendance_manage


__all__ = (meeting_manage, user_manage, message_manage,attendance_manage)
