import pytest
from django.db import IntegrityError

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile


@pytest.mark.django_db
class TestWallProfile:
    """Tests for WallProfile model"""

    def test_profile_creation(self):
        """Test creating a wall profile"""
        profile = WallProfile.objects.create(
            name="Test Profile 1",
            profile_number=1,
        )
        assert profile.name == "Test Profile 1"
        assert profile.profile_number == 1
        assert str(profile) == "Test Profile 1"

    def test_profile_number_unique(self):
        """Test that profile_number must be unique"""
        WallProfile.objects.create(name="Profile 1", profile_number=1)

        with pytest.raises(IntegrityError):
            WallProfile.objects.create(name="Profile 2", profile_number=1)

    def test_total_cost_no_logs(self, wall_profile):
        """Test total cost calculation with no logs"""
        cost = wall_profile.total_cost()
        assert cost == 0

    def test_total_cost_with_logs(self, wall_profile):
        """Test total cost calculation with logs"""
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=585)
        DailyLog.objects.create(profile=wall_profile, day_number=2, ice_used=585)

        # Total: 1170 cubic yards * 1900 = 2,223,000
        cost = wall_profile.total_cost()
        assert cost == 2_223_000  # noqa: PLR2004

    def test_total_cost_up_to_specific_day(self, wall_profile):
        """Test total cost calculation up to a specific day"""
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=585)
        DailyLog.objects.create(profile=wall_profile, day_number=2, ice_used=585)
        DailyLog.objects.create(profile=wall_profile, day_number=3, ice_used=390)

        # Cost up to day 2: 1170 * 1900 = 2,223,000
        cost = wall_profile.total_cost(day=2)
        assert cost == 2_223_000  # noqa: PLR2004

        # Cost up to day 1: 585 * 1900 = 1,111,500
        cost = wall_profile.total_cost(day=1)
        assert cost == 1_111_500  # noqa: PLR2004

    def test_total_cost_day_zero(self, wall_profile):
        """Test total cost at day 0 is zero"""
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=585)

        cost = wall_profile.total_cost(day=0)
        assert cost == 0


@pytest.mark.django_db
class TestDailyLog:
    """Tests for DailyLog model"""

    def test_daily_log_creation(self, wall_profile):
        """Test creating a daily log"""
        log = DailyLog.objects.create(
            profile=wall_profile,
            day_number=1,
            ice_used=585,
        )
        assert log.profile == wall_profile
        assert log.day_number == 1
        assert log.ice_used == 585  # noqa: PLR2004
        assert str(log) == "Day 1 - Test Profile"

    def test_unique_together_constraint(self, wall_profile):
        """Test that profile and day_number must be unique together"""
        DailyLog.objects.create(
            profile=wall_profile,
            day_number=1,
            ice_used=585,
        )

        # Attempting to create another log for same profile and day should fail
        with pytest.raises(IntegrityError):
            DailyLog.objects.create(
                profile=wall_profile,
                day_number=1,
                ice_used=390,
            )

    def test_ordering(self, wall_profile):
        """Test that logs are ordered by day_number"""
        DailyLog.objects.create(profile=wall_profile, day_number=3, ice_used=100)
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=200)
        DailyLog.objects.create(profile=wall_profile, day_number=2, ice_used=300)

        logs = list(wall_profile.logs.all())
        assert logs[0].day_number == 1
        assert logs[1].day_number == 2  # noqa: PLR2004
        assert logs[2].day_number == 3  # noqa: PLR2004
