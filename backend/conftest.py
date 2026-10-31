import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# This makes the pytest-asyncio plugin work properly
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(autouse=True)
def mock_beanie_document_init():
    # Mock the Document class to prevent CollectionWasNotInitialized
    from app.models.laboratory_test import LaboratoryTest
    from app.models.laboratory_booking import LaboratoryBooking
    from app.models.report import Report
    from app.models.care_plan import CarePlan, CarePlanHistory
    from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress

    # Create mock settings for LaboratoryTest
    mock_test_settings = MagicMock()
    mock_test_settings.pymongo_collection = "laboratory_tests"

    # Create mock settings for LaboratoryBooking
    mock_booking_settings = MagicMock()
    mock_booking_settings.pymongo_collection = "laboratory_bookings"

    # Create mock settings for Report
    mock_report_settings = MagicMock()
    mock_report_settings.pymongo_collection = "reports"

    # Create mock settings for CarePlan
    mock_cp_settings = MagicMock()
    mock_cp_settings.pymongo_collection = "care_plans"

    # Create mock settings for CarePlanHistory
    mock_history_settings = MagicMock()
    mock_history_settings.pymongo_collection = "care_plan_histories"

    # Create mock settings for Exercise
    mock_ex_settings = MagicMock()
    mock_ex_settings.pymongo_collection = "exercises"

    # Create mock settings for ExerciseAssignment
    mock_ex_assign_settings = MagicMock()
    mock_ex_assign_settings.pymongo_collection = "exercise_assignments"

    # Create mock settings for ExerciseProgress
    mock_ex_progress_settings = MagicMock()
    mock_ex_progress_settings.pymongo_collection = "exercise_progress"

    # Patch the get_settings method on each class to return our mock settings
    with patch.object(LaboratoryTest, 'get_settings', return_value=mock_test_settings):
        with patch.object(LaboratoryBooking, 'get_settings', return_value=mock_booking_settings):
            with patch.object(Report, 'get_settings', return_value=mock_report_settings):
                with patch.object(CarePlan, 'get_settings', return_value=mock_cp_settings):
                    with patch.object(CarePlanHistory, 'get_settings', return_value=mock_history_settings):
                        with patch.object(Exercise, 'get_settings', return_value=mock_ex_settings):
                            with patch.object(ExerciseAssignment, 'get_settings', return_value=mock_ex_assign_settings):
                                with patch.object(ExerciseProgress, 'get_settings', return_value=mock_ex_progress_settings):
                                    # Also mock beanie.init_beanie to do nothing
                                    with patch('beanie.init_beanie', new_callable=AsyncMock) as mock_init:
                                        mock_init.return_value = None
                                        yield
