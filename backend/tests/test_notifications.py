import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from beanie import PydanticObjectId

from app.core.time import utc_now
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService
from app.api.notifications import list_notifications, get_unread_count, mark_read, mark_all_read
from fastapi import HTTPException


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


@pytest.mark.asyncio
async def test_mark_all_read_service():
    with patch("app.services.notification_service.NotificationRepository") as mock_repo:
        mock_repo.mark_all_as_read = AsyncMock(return_value=3)

        result = await NotificationService.mark_all_read("000000000000000000000000")
        assert result == 3
        mock_repo.mark_all_as_read.assert_called_once_with("000000000000000000000000")


@pytest.mark.asyncio
async def test_list_notifications_api_endpoint():
    mock_notif = MagicMock(spec=Notification)
    mock_notif.id = PydanticObjectId("111111111111111111111111")
    mock_notif.recipient_user_id = PydanticObjectId("000000000000000000000000")
    mock_notif.title = "Appointment Confirmed"
    mock_notif.message = "Your visit is confirmed."
    mock_notif.notification_type = "appointment"
    mock_notif.is_read = False
    mock_notif.related_entity_id = "apt_1"
    mock_notif.created_at = utc_now()

    mock_user = MagicMock(spec=User)
    mock_user.id = PydanticObjectId("000000000000000000000000")

    with patch("app.api.notifications.NotificationService.get_user_notifications", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [mock_notif]

        response = await list_notifications(current_user=mock_user)
        assert len(response) == 1
        assert response[0].title == "Appointment Confirmed"
        assert response[0].recipient_user_id == "000000000000000000000000"
        assert response[0].is_read is False
        mock_get.assert_called_once_with("000000000000000000000000")


@pytest.mark.asyncio
async def test_get_unread_count_api_endpoint():
    mock_user = MagicMock(spec=User)
    mock_user.id = PydanticObjectId("000000000000000000000000")

    with patch("app.api.notifications.NotificationService.get_unread_count", new_callable=AsyncMock) as mock_count:
        mock_count.return_value = 4

        response = await get_unread_count(current_user=mock_user)
        assert response == {"count": 4}
        mock_count.assert_called_once_with("000000000000000000000000")


@pytest.mark.asyncio
async def test_mark_read_api_endpoint_success():
    mock_notif = MagicMock(spec=Notification)
    mock_notif.id = PydanticObjectId("111111111111111111111111")
    mock_notif.recipient_user_id = PydanticObjectId("000000000000000000000000")
    mock_notif.title = "Lab Released"
    mock_notif.message = "Results published."
    mock_notif.notification_type = "laboratory"
    mock_notif.is_read = True
    mock_notif.related_entity_id = "lab_1"
    mock_notif.created_at = utc_now()

    mock_user = MagicMock(spec=User)
    mock_user.id = PydanticObjectId("000000000000000000000000")

    with patch("app.api.notifications.NotificationService.mark_as_read", new_callable=AsyncMock) as mock_mark:
        mock_mark.return_value = mock_notif

        response = await mark_read(notification_id="111111111111111111111111", current_user=mock_user)
        assert response.is_read is True
        assert response.title == "Lab Released"
        mock_mark.assert_called_once_with("111111111111111111111111", "000000000000000000000000")


@pytest.mark.asyncio
async def test_mark_read_api_endpoint_unauthorized_or_not_found():
    mock_user = MagicMock(spec=User)
    mock_user.id = PydanticObjectId("000000000000000000000000")

    with patch("app.api.notifications.NotificationService.mark_as_read", new_callable=AsyncMock) as mock_mark:
        mock_mark.return_value = None

        with pytest.raises(HTTPException) as exc:
            await mark_read(notification_id="999999999999999999999999", current_user=mock_user)
        assert exc.value.status_code == 404
        assert "not found or access denied" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_mark_all_read_api_endpoint():
    mock_user = MagicMock(spec=User)
    mock_user.id = PydanticObjectId("000000000000000000000000")

    with patch("app.api.notifications.NotificationService.mark_all_read", new_callable=AsyncMock) as mock_all:
        mock_all.return_value = 5

        response = await mark_all_read(current_user=mock_user)
        assert response["count"] == 5
        assert "marked as read" in response["message"]
        mock_all.assert_called_once_with("000000000000000000000000")

