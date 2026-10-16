from typing import List, Optional
from beanie import PydanticObjectId
from app.models.notification import Notification

class NotificationRepository:
    @staticmethod
    async def create(notification: Notification) -> Notification:
        return await notification.insert()

    @staticmethod
    async def get_by_id(id: str) -> Optional[Notification]:
        return await Notification.get(PydanticObjectId(id))

    @staticmethod
    async def list_by_recipient_id(recipient_user_id: str) -> List[Notification]:
        return await Notification.find(
            Notification.recipient_user_id == PydanticObjectId(recipient_user_id)
        ).sort(-Notification.created_at).to_list()

    @staticmethod
    async def get_unread_count(recipient_user_id: str) -> int:
        return await Notification.find(
            Notification.recipient_user_id == PydanticObjectId(recipient_user_id),
            Notification.is_read == False
        ).count()

    @staticmethod
    async def mark_all_as_read(recipient_user_id: str) -> int:
        result = await Notification.find(
            Notification.recipient_user_id == PydanticObjectId(recipient_user_id),
            Notification.is_read == False
        ).update({"$set": {"is_read": True}})
        return result.modified_count
