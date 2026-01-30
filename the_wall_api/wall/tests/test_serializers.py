import pytest

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.serializers import DailyIceSerializer
from the_wall_api.wall.serializers import GlobalOverviewSerializer
from the_wall_api.wall.serializers import ProfileOverviewSerializer


class TestDailyIceSerializer:
    """Tests for DailyIceSerializer"""

    def test_serializer_with_data(self):
        """Test serializer with valid data"""
        data = {"day": "1", "ice_amount": "585"}
        serializer = DailyIceSerializer(data)

        assert serializer.data["day"] == "1"
        assert serializer.data["ice_amount"] == "585"

    def test_serializer_day_as_string(self):
        """Test that day is serialized as string"""
        data = {"day": 5, "ice_amount": 1000}
        serializer = DailyIceSerializer(data)

        # Even though we pass int, it should be string
        assert isinstance(serializer.data["day"], str)


@pytest.mark.django_db
class TestProfileOverviewSerializer:
    """Tests for ProfileOverviewSerializer"""

    def test_serializer_without_day_context(self, wall_profile_with_logs):
        """Test serializer returns total cost when no day specified"""
        serializer = ProfileOverviewSerializer(wall_profile_with_logs)

        assert serializer.data["day"] == "None"
        # (585 + 585 + 390) * 1900 = 2,964,000
        assert serializer.data["cost"] == "2,964,000"

    def test_serializer_with_day_context(self, wall_profile_with_logs):
        """Test serializer returns cost up to specific day"""
        serializer = ProfileOverviewSerializer(
            wall_profile_with_logs,
            context={"day_number": 2},
        )

        assert serializer.data["day"] == "2"
        # (585 + 585) * 1900 = 2,223,000
        assert serializer.data["cost"] == "2,223,000"

    def test_serializer_with_day_one(self, wall_profile_with_logs):
        """Test serializer at day 1"""
        serializer = ProfileOverviewSerializer(
            wall_profile_with_logs,
            context={"day_number": 1},
        )

        assert serializer.data["day"] == "1"
        # 585 * 1900 = 1,111,500
        assert serializer.data["cost"] == "1,111,500"

    def test_serializer_empty_profile(self, empty_wall_profile):
        """Test serializer with profile that has no logs"""
        serializer = ProfileOverviewSerializer(empty_wall_profile)

        assert serializer.data["day"] == "None"
        assert serializer.data["cost"] == "0"

    def test_serializer_cost_formatting(self, wall_profile):
        """Test that cost is formatted with commas"""
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=10000)

        serializer = ProfileOverviewSerializer(wall_profile)

        # 10000 * 1900 = 19,000,000
        assert "," in serializer.data["cost"]
        assert serializer.data["cost"] == "19,000,000"


@pytest.mark.django_db
class TestGlobalOverviewSerializer:
    """Tests for GlobalOverviewSerializer"""

    def test_serializer_with_day_one(self, multiple_profiles_with_logs):
        """Test serializer at day 1 (Matches Task Example with 9+ workers)"""
        logs = DailyLog.objects.all()
        serializer = GlobalOverviewSerializer(logs, context={"day_number": 1})

        assert serializer.data["day"] == "1"
        # (585 + 195 + 975) * 1900 = 3,334,500
        assert serializer.data["cost"] == "3,334,500"

    def test_serializer_with_day_two(self, multiple_profiles_with_logs):
        """Test serializer at day 2"""
        logs = DailyLog.objects.all()
        serializer = GlobalOverviewSerializer(logs, context={"day_number": 2})

        assert serializer.data["day"] == "2"
        # Day 1: 1755 + Day 2: (585 + 975) = 3,315 total ice
        # 3,315 * 1900 = 6,298,500
        assert serializer.data["cost"] == "6,298,500"

    def test_serializer_without_day_context(self, multiple_profiles_with_logs):
        """Test serializer returns total cost for everything in the fixture"""
        logs = DailyLog.objects.all()
        serializer = GlobalOverviewSerializer(logs)

        assert serializer.data["day"] == "None"
        # Grand total of all logs in fixture: 8,151,000
        assert serializer.data["cost"] == "8,151,000"

    def test_serializer_empty_queryset(self):
        """Test serializer with no logs"""
        logs = DailyLog.objects.none()
        serializer = GlobalOverviewSerializer(logs)

        assert serializer.data["day"] == "None"
        assert serializer.data["cost"] == "0"

    def test_serializer_filters_by_day(self, wall_profile):
        """Test that serializer properly filters by day_number"""
        DailyLog.objects.create(profile=wall_profile, day_number=1, ice_used=100)
        DailyLog.objects.create(profile=wall_profile, day_number=2, ice_used=200)
        DailyLog.objects.create(profile=wall_profile, day_number=3, ice_used=300)

        logs = DailyLog.objects.all()
        serializer = GlobalOverviewSerializer(logs, context={"day_number": 2})

        # Should only include days 1 and 2: (100 + 200) * 1900 = 570,000
        assert serializer.data["cost"] == "570,000"
