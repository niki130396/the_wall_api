import pytest
from django.urls import reverse
from rest_framework import status

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile


@pytest.mark.django_db
class TestDailyIceAPI:
    """Test the daily ice API endpoint:
    /api/profiles/{profile_number}/days/{day_number}/"""

    def test_get_daily_ice_existing_day(self, auth_client, wall_profile_with_logs):
        """Test getting ice amount for an existing day"""
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 1, "day_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "1"
        assert response.data["ice_amount"] == "585"

    def test_get_daily_ice_different_days(self, auth_client, wall_profile_with_logs):
        """Test getting ice amount for different days"""
        # Day 2
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 1, "day_number": 2},
        )
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["ice_amount"] == "585"

        # Day 3
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 1, "day_number": 3},
        )
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["ice_amount"] == "390"

    def test_get_daily_ice_non_existing_day(self, auth_client, wall_profile_with_logs):
        """Test getting ice amount for a non-existing day returns 0"""
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 1, "day_number": 99},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "99"
        assert response.data["ice_amount"] == "0"

    def test_get_daily_ice_invalid_profile(self, auth_client):
        """Test getting ice amount for non-existing profile"""
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 999, "day_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProfileOverviewAPI:
    """Test the profile overview API endpoint:
    /api/profiles/{profile_number}/overview/{day_number}/"""

    def test_profile_overview_total(self, auth_client, wall_profile_with_logs):
        """Test getting total cost for a profile (no day specified)"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "None"
        # Total: (585 + 585 + 390) * 1900 = 2,964,000 noqa ERA001
        assert response.data["cost"] == "2,964,000"

    def test_profile_overview_up_to_specific_day(
        self,
        auth_client,
        wall_profile_with_logs,
    ):
        """Test getting cost for a profile up to a specific day"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 1, "day_number": 2},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "2"
        # Up to day 2: (585 + 585) * 1900 = 2,223,000 noqa ERA001
        assert response.data["cost"] == "2,223,000"

    def test_profile_overview_day_one(self, auth_client, wall_profile_with_logs):
        """Test getting cost for a profile at day 1"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 1, "day_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "1"
        # Day 1: 585 * 1900 = 1,111,500 noqa ERA001
        assert response.data["cost"] == "1,111,500"

    def test_profile_overview_day_zero(self, auth_client, wall_profile_with_logs):
        """Test getting cost for a profile at day 0"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 1, "day_number": 0},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "None"
        assert response.data["cost"] == "0"

    def test_profile_overview_invalid_profile(self, auth_client):
        """Test getting overview for non-existing profile"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 999},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_profile_overview_no_logs(self, auth_client, empty_wall_profile):
        """Test profile overview with no logs"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 99},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cost"] == "0"


@pytest.mark.django_db
class TestGlobalOverviewAPI:
    """Test the global overview API endpoint: /api/profiles/overview/{day_number}/"""

    def test_global_overview_total(self, auth_client, multiple_profiles_with_logs):
        """Test getting total cost for all profiles (no day specified)"""
        url = reverse("api:profiles-overview")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "None"
        # Corrected Total: 4,290 yards * 1,900 = 8,151,000 noqa ERA001
        assert response.data["cost"] == "8,151,000"

    def test_global_overview_day_one(self, auth_client, multiple_profiles_with_logs):
        """Test getting total cost up to day 1"""
        url = reverse("api:profiles-overview", kwargs={"day_number": 1})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "1"
        # Day 1: (585+195+975) * 1900 = 3,334,500 noqa ERA001
        assert response.data["cost"] == "3,334,500"

    def test_global_overview_day_two(self, auth_client, multiple_profiles_with_logs):
        """Test getting total cost up to day 2"""
        url = reverse("api:profiles-overview", kwargs={"day_number": 2})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "2"
        # Day 1: 1,755 + Day 2: (585 + 975) = 3,315 yards noqa ERA001
        # 3,315 * 1,900 = 6,298,500 noqa ERA001
        assert response.data["cost"] == "6,298,500"

    def test_global_overview_no_data(self, auth_client):
        """Test global overview with no logs at all"""
        url = reverse("api:profiles-overview")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cost"] == "0"

    def test_global_overview_day_zero(self, auth_client, multiple_profiles_with_logs):
        """Test global overview at day 0"""
        url = reverse("api:profiles-overview", kwargs={"day_number": 0})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "0"
        assert response.data["cost"] == "0"


@pytest.mark.django_db
class TestTaskExampleScenario:
    """Integration tests matching the exact task example"""

    @pytest.fixture(autouse=True)
    def setup_task_example(self):
        """Set up the exact example from task description"""
        # Profile 1: 21 25 28 (needs 9, 5, 2 days) noqa ERA001
        profile1 = WallProfile.objects.create(name="Profile 1", profile_number=1)
        DailyLog.objects.create(profile=profile1, day_number=1, ice_used=585)

        # Profile 2: 17 (needs 13 days) noqa ERA001
        profile2 = WallProfile.objects.create(name="Profile 2", profile_number=2)
        DailyLog.objects.create(profile=profile2, day_number=1, ice_used=195)

        # Profile 3: 17 22 17 19 17 (needs 13, 8, 13, 11, 13 days) noqa ERA001
        profile3 = WallProfile.objects.create(name="Profile 3", profile_number=3)
        DailyLog.objects.create(profile=profile3, day_number=1, ice_used=975)

    def test_example_get_profile_1_day_1(self, auth_client):
        """Test: GET /api/profiles/1/days/1/ -> {day: "1", ice_amount: "585"}"""
        url = reverse(
            "api:profiles-daily-ice",
            kwargs={"profile_number": 1, "day_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"day": "1", "ice_amount": "585"}

    def test_example_get_profile_1_overview_day_1(self, auth_client):
        """Test: GET /api/profiles/1/overview/1/ -> {day: "1", cost: "1,111,500"}"""
        url = reverse(
            "api:profiles-profile-overview",
            kwargs={"profile_number": 1, "day_number": 1},
        )
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "1"
        assert response.data["cost"] == "1,111,500"

    def test_example_get_global_overview_day_1(self, auth_client):
        """Test: GET /api/profiles/overview/1/ -> {day: "1", cost: "3,334,500"}"""
        url = reverse("api:profiles-overview", kwargs={"day_number": 1})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["day"] == "1"
        assert response.data["cost"] == "3,334,500"
