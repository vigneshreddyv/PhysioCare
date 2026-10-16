import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from beanie import PydanticObjectId

from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.api.notifications import list_notifications, get_unread_count, mark_read, mark_all_read


@pytest.fixture(autouse=True)
def mock_notification_settings():
    mock_settings = MagicMock()
    mock_settings.pymongo_collection = "notifications"
    with patch("app.models.notification.Notification.get_settings", return_value=mock_settings):
        yield


def test_notification_model_creation():
    data = {
        "recipient_user_id": PydanticObjectId("000000000000000000000000"),
        "title": "Test Title",
        "message": "Test Message",
        "notification_type": "general",
        "is_read": False,
        "related_entity_id": "12345"
    }
    notification = Notification.model_validate(data)
    assert str(notification.recipient_user_id) == "000000000000000000000000"
    assert notification.title == "Test Title"
    assert notification.message == "Test Message"
    assert notification.notification_type == "general"
    assert notification.is_read is False
    assert notification.related_entity_id == "12345"
    assert notification.created_at is not None


@pytest.mark.asyncio
async def test_create_notification_service():
    mock_notif = MagicMock(spec=Notification)
    mock_notif.id = PydanticObjectId("111111111111111111111111")
    mock_notif.recipient_user_id = PydanticObjectId("000000000000000000000000")
    mock_notif.title = "Test"
    mock_notif.message = "Message"

    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.create = AsyncMock(return_value=mock_notif)

        result = await NotificationService.create_notification(
            recipient_user_id="000000000000000000000000",
            title="Test",
            message="Message"
        )
        assert result == mock_notif
        mock_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_notifications_service():
    mock_notif = MagicMock()
    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.list_by_recipient_id = AsyncMock(return_value=[mock_notif])

        result = await NotificationService.get_user_notifications("000000000000000000000000")
        assert result == [mock_notif]
        mock_repo.list_by_recipient_id.assert_called_once_with("000000000000000000000000")


@pytest.mark.asyncio
async def test_get_unread_count_service():
    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.get_unread_count = AsyncMock(return_value=5)

        result = await NotificationService.get_unread_count("000000000000000000000000")
        assert result == 5
        mock_repo.get_unread_count.assert_called_once_with("000000000000000000000000")


@pytest.mark.asyncio
async def test_mark_as_read_service_success():
    mock_notif = MagicMock()
    mock_notif.recipient_user_id = PydanticObjectId("000000000000000000000000")
    mock_notif.save = AsyncMock()

    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=mock_notif)

        result = await NotificationService.mark_as_read("111111111111111111111111", "000000000000000000000000")
        assert result.is_read is True
        mock_notif.save.assert_called_once()


@pytest.mark.asyncio
async def test_mark_as_read_service_unauthorized():
    mock_notif = MagicMock()
    mock_notif.recipient_user_id = PydanticObjectId("222222222222222222222222") # Different user

    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=mock_notif)

        result = await NotificationService.mark_as_read("111111111111111111111111", "000000000000000000000000")
        assert result is None
