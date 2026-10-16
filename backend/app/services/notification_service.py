from typing import List, Optional
from beanie import PydanticObjectId
from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository

class NotificationService:
    @staticmethod
    async def create_notification(
        recipient_user_id: str,
        title: str,
        message: str,
        notification_type: str = "general",
        related_entity_id: Optional[str] = None
    ) -> Notification:
        notif = Notification(
            recipient_user_id=PydanticObjectId(recipient_user_id),
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_id=related_entity_id
        )
        return await NotificationRepository.create(notif)

    @staticmethod
    async def get_user_notifications(user_id: str) -> List[Notification]:
        return await NotificationRepository.list_by_recipient_id(user_id)

    @staticmethod
    async def get_unread_count(user_id: str) -> int:
        return await NotificationRepository.get_unread_count(user_id)

    @staticmethod
    async def mark_as_read(notification_id: str, user_id: str) -> Optional[Notification]:
        notif = await NotificationRepository.get_by_id(notification_id)
        if not notif or str(notif.recipient_user_id) != user_id:
            return None
        notif.is_read = True
        await notif.save()
        return notif

    @staticmethod
    async def mark_all_read(user_id: str) -> int:
        return await NotificationRepository.mark_all_as_read(user_id)
