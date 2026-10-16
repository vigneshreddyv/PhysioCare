from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    current_user: User = Depends(get_current_user)
):
    notifications = await NotificationService.get_user_notifications(str(current_user.id))
    return [
        NotificationOut(
            id=str(n.id),
            recipient_user_id=str(n.recipient_user_id),
            title=n.title,
            message=n.message,
            notification_type=n.notification_type,
            is_read=n.is_read,
            related_entity_id=n.related_entity_id,
            created_at=n.created_at
        ) for n in notifications
    ]

@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user)
):
    count = await NotificationService.get_unread_count(str(current_user.id))
    return {"count": count}

@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user)
):
    n = await NotificationService.mark_as_read(notification_id, str(current_user.id))
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied"
        )
    return NotificationOut(
        id=str(n.id),
        recipient_user_id=str(n.recipient_user_id),
        title=n.title,
        message=n.message,
        notification_type=n.notification_type,
        is_read=n.is_read,
        related_entity_id=n.related_entity_id,
        created_at=n.created_at
    )

@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user)
):
    modified = await NotificationService.mark_all_read(str(current_user.id))
    return {"message": "All notifications marked as read", "count": modified}
