import pytest
from rest_framework.test import APIClient

from the_wall_api.users.models import User
from the_wall_api.users.tests.factories import UserFactory
from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory()


@pytest.fixture
def api_client():
    """Fixture for DRF API client"""
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """An API client with a logged-in user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def wall_profile():
    """Fixture for a basic wall profile"""
    return WallProfile.objects.create(
        name="Test Profile",
        profile_number=1,
    )


@pytest.fixture
def wall_profile_with_logs(wall_profile):
    """Fixture for a wall profile with daily logs"""
    DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=585)
    DailyLog.objects.create(profile=wall_profile, day_number=2, ice_used=585)
    DailyLog.objects.create(profile=wall_profile, day_number=3, ice_used=390)
    return wall_profile


@pytest.fixture
def multiple_profiles_with_logs():
    """Fixture for multiple profiles with logs (task example scenario)"""
    # Profile 1: 21 25 28 (3 sections)
    profile1 = WallProfile.objects.create(name="Profile 1", profile_number=1)
    DailyLog.objects.create(profile=profile1, day_number=1, ice_used=585)
    DailyLog.objects.create(profile=profile1, day_number=2, ice_used=585)

    # Profile 2: 17 (1 section)
    profile2 = WallProfile.objects.create(name="Profile 2", profile_number=2)
    DailyLog.objects.create(profile=profile2, day_number=1, ice_used=195)

    # Profile 3: 17 22 17 19 17 (5 sections)
    profile3 = WallProfile.objects.create(name="Profile 3", profile_number=3)
    DailyLog.objects.create(profile=profile3, day_number=1, ice_used=975)
    DailyLog.objects.create(profile=profile3, day_number=2, ice_used=975)
    DailyLog.objects.create(profile=profile3, day_number=3, ice_used=975)

    return [profile1, profile2, profile3]


@pytest.fixture
def empty_wall_profile():
    """Fixture for a wall profile with no logs"""
    return WallProfile.objects.create(
        name="Empty Profile",
        profile_number=99,
    )
