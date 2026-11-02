from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from beanie import PydanticObjectId

from app.api.users import list_doctors
from app.core.pagination import PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.doctor import Doctor
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


def aggregate_collection(rows=None):
    collection = MagicMock()
    collection.aggregate.return_value.to_list = AsyncMock(return_value=rows or [])
    return collection


@pytest.mark.asyncio
async def test_admin_directory_route_always_uses_bounded_search(monkeypatch):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "search_doctors", search)

    result = await list_doctors(
        current_user=SimpleNamespace(role="admin"),
        page=21,
        page_size=50,
        search=None,
        home_visits_only=False,
    )

    assert result == []
    search.assert_awaited_once_with(
        "", PageWindow(21, 50), home_visits_only=False,
    )


@pytest.mark.asyncio
async def test_admin_directory_http_role_boundary(monkeypatch):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "search_doctors", search)
    try:
        for role, expected in (("admin", 200), ("patient", 403), ("doctor", 403), ("receptionist", 403)):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
                id=PydanticObjectId("507f1f77bcf86cd799439011"),
                role=role,
                is_active=True,
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver",
            ) as client:
                response = await client.get(
                    "/api/users/doctors",
                    params={"search": "Fictional", "page": 25, "page_size": 50},
                )
            assert response.status_code == expected
    finally:
        app.dependency_overrides.clear()

    search.assert_awaited_once_with(
        "Fictional", PageWindow(25, 50), home_visits_only=False,
    )


@pytest.mark.asyncio
async def test_admin_directory_search_filters_before_stable_page_and_projects_only_output(monkeypatch):
    collection = aggregate_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    assert await ProfileRepository.search_doctors(
        "Fictional.*Specialist", PageWindow(25, 50),
    ) == []

    collection.aggregate.assert_called_once()
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"role": "doctor"}}
    search_index = next(i for i, stage in enumerate(pipeline) if "$or" in stage.get("$match", {}))
    sort_index = next(i for i, stage in enumerate(pipeline) if "$sort" in stage)
    skip_index = next(i for i, stage in enumerate(pipeline) if "$skip" in stage)
    project_index = next(i for i, stage in enumerate(pipeline) if "$project" in stage)
    assert search_index < sort_index < skip_index < project_index
    predicates = pipeline[search_index]["$match"]["$or"]
    assert {next(iter(predicate)) for predicate in predicates} == {
        "full_name",
        "email",
        "profile.specialization",
        "profile.qualifications",
        "profile.specialties",
    }
    assert all(
        next(iter(predicate.values()))["$regex"] == r"Fictional\.\*Specialist"
        for predicate in predicates
    )
    assert pipeline[sort_index] == {"$sort": {"full_name": 1, "_id": 1}}
    assert pipeline[skip_index] == {"$skip": 1200}
    assert pipeline[skip_index + 1] == {"$limit": 50}
    projection = pipeline[project_index]["$project"]
    assert "profile" not in projection
    assert set(projection) == {
        "_id", "email", "full_name", "profile._id", "profile.user_id",
        "profile.specialization", "profile.profile_image", "profile.bio",
        "profile.qualifications", "profile.years_experience", "profile.specialties",
        "profile.linkedin_url", "profile.website_url", "profile.is_active_today",
        "profile.accepts_home_visits",
    }
    collection.aggregate.return_value.to_list.assert_awaited_once_with(length=50)
    collection.find.assert_not_called()


@pytest.mark.asyncio
async def test_admin_directory_large_synthetic_dataset_returns_only_requested_page(monkeypatch):
    rows = [
        {
            "_id": f"user-{index}",
            "full_name": f"Fictional Clinician {index:04d}",
            "email": f"clinician{index}@example.com",
            "profile": {
                "_id": f"doctor-{index}",
                "user_id": f"user-{index}",
                "specialization": "Fictional rehabilitation",
                "is_active_today": True,
                "accepts_home_visits": True,
            },
        }
        for index in range(1250)
    ]
    collection = aggregate_collection(rows[1200:1250])
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)
    monkeypatch.setattr(Doctor, "model_validate", staticmethod(lambda profile: SimpleNamespace(
        id=profile["_id"],
        user_id=profile["user_id"],
        specialization=profile["specialization"],
        is_active_today=profile["is_active_today"],
        accepts_home_visits=profile["accepts_home_visits"],
    )))

    result = await ProfileRepository.search_doctors("", PageWindow(25, 50))

    assert len(result) == 50
    assert result[0][1].full_name == "Fictional Clinician 1200"
    assert result[-1][1].full_name == "Fictional Clinician 1249"
    pipeline = collection.aggregate.call_args.args[0]
    assert {"$skip": 1200} in pipeline
    assert {"$limit": 50} in pipeline
    collection.aggregate.return_value.to_list.assert_awaited_once_with(length=50)


@pytest.mark.asyncio
async def test_admin_directory_returns_large_dataset_page_without_n_plus_one(monkeypatch):
    user_id = PydanticObjectId("507f1f77bcf86cd799439020")
    doctor_id = PydanticObjectId("507f1f77bcf86cd799439021")
    doctor = SimpleNamespace(
        id=doctor_id,
        user_id=user_id,
        specialization="Fictional rehabilitation",
        profile_image=None,
        bio=None,
        qualifications="Fictional qualification",
        years_experience=7,
        specialties=["Fictional focus"],
        linkedin_url=None,
        website_url=None,
        is_active_today=True,
        accepts_home_visits=True,
    )
    user = SimpleNamespace(
        id=user_id,
        full_name="Fictional Clinician 1201",
        email="clinician1201@example.invalid",
    )
    repository_search = AsyncMock(return_value=[(doctor, user)])
    n_plus_one_lookup = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "search_doctors", repository_search)
    monkeypatch.setattr(UserRepository, "get_by_id", n_plus_one_lookup)

    result = await UserService.search_doctors("1201", PageWindow(25, 50))

    repository_search.assert_awaited_once_with(
        "1201", PageWindow(25, 50), active_only=False, home_visits_only=False,
    )
    n_plus_one_lookup.assert_not_awaited()
    assert len(result) == 1
    assert result[0].id == str(doctor_id)
    assert result[0].full_name == "Fictional Clinician 1201"
    assert result[0].email == "clinician1201@example.invalid"
    assert set(result[0].model_dump()) == {
        "id", "full_name", "email", "is_active_today", "specialization",
        "profile_image", "bio", "qualifications", "years_experience", "specialties",
        "linkedin_url", "website_url", "accepts_home_visits",
    }


@pytest.mark.asyncio
async def test_admin_directory_empty_page_does_not_fall_back_to_full_collection(monkeypatch):
    repository_search = AsyncMock(return_value=[])
    legacy_profiles = AsyncMock()
    legacy_users = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "search_doctors", repository_search)
    monkeypatch.setattr(ProfileRepository, "list_doctors", legacy_profiles)
    monkeypatch.setattr(UserRepository, "get_by_id", legacy_users)

    assert await UserService.search_doctors("no match", PageWindow(1, 50)) == []
    repository_search.assert_awaited_once()
    legacy_profiles.assert_not_awaited()
    legacy_users.assert_not_awaited()

