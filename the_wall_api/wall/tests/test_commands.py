"""
Tests for wall management commands.

To run all tests:
    pytest the_wall_api/wall/tests/test_commands.py

To skip slow tests (recommended for regular development):
    pytest the_wall_api/wall/tests/test_commands.py -m "not slow"

To run only slow tests:
    pytest the_wall_api/wall/tests/test_commands.py -m "slow"
"""

import logging
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
class TestLoadWallConfigCommand:
    """Tests for load_wall_config management command"""

    def test_load_simple_config(self):
        """Test loading a simple wall configuration"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("21 25 28\n")
            f.write("17\n")
            f.write("17 22 17 19 17\n")
            f.write("3\n")  # Number of teams
            config_path = f.name

        try:
            call_command("load_wall_config", config_path, "--teams", "3")

            # Verify profiles were created
            assert WallProfile.objects.count() == 3  # noqa: PLR2004

            profile1 = WallProfile.objects.get(profile_number=1)
            profile2 = WallProfile.objects.get(profile_number=2)
            profile3 = WallProfile.objects.get(profile_number=3)

            assert profile1.name == "Profile 1"
            assert profile2.name == "Profile 2"
            assert profile3.name == "Profile 3"

            # Verify daily logs were created
            assert DailyLog.objects.filter(profile=profile1).exists()
            assert DailyLog.objects.filter(profile=profile2).exists()
            assert DailyLog.objects.filter(profile=profile3).exists()

            # Verify that Profile 1 is eventually worked on
            profile1_logs = DailyLog.objects.filter(profile=profile1)
            assert profile1_logs.exists()

            # If you want to check the first day it was worked on:
            first_log = profile1_logs.order_by("day_number").first()
            assert first_log.ice_used == 195  # noqa: PLR2004

        finally:
            Path(config_path).unlink()

    def test_load_config_with_different_team_count(self):
        """Test loading config with custom team count"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("20 20 20\n")
            f.write("5\n")  # Default from file
            config_path = f.name

        try:
            call_command("load_wall_config", config_path, "--teams", "2")

            assert WallProfile.objects.count() == 1

            profile = WallProfile.objects.get(profile_number=1)
            logs = DailyLog.objects.filter(profile=profile)
            assert logs.exists()

            # With 2 teams working on 3 sections (each needs 10 days)
            # Day 1-5: 2 crews working -> 2 * 195 = 390 ice per day
            # Day 6-10: 1 crew working -> 1 * 195 = 195 ice per day
            assert logs.count() == 15  # noqa: PLR2004

        finally:
            Path(config_path).unlink()

    def test_load_config_empty_file(self):
        """Test loading an empty config file raises error"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="empty"):
                call_command("load_wall_config", config_path)

        finally:
            Path(config_path).unlink()

    def test_load_config_sections_reach_max_height(self):
        """Test that sections reaching 30 feet stop construction"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("29 29\n")  # Two sections at 29 feet
            f.write("2\n")  # 2 teams
            config_path = f.name

        try:
            call_command("load_wall_config", config_path, "--teams", "2")

            profile = WallProfile.objects.get(profile_number=1)

            # Should only have 1 day of logs (both sections reach 30 after 1 day)
            logs = DailyLog.objects.filter(profile=profile)
            assert logs.count() == 1

            day1 = logs.get(day_number=1)
            assert day1.ice_used == 390  # noqa: PLR2004 2 crews * 195

        finally:
            Path(config_path).unlink()

    def test_load_config_already_complete_sections(self):
        """Test sections already at 30 feet are skipped"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("30 30 25\n")  # Two complete, one needs work
            f.write("3\n")
            config_path = f.name

        try:
            call_command("load_wall_config", config_path, "--teams", "3")

            profile = WallProfile.objects.get(profile_number=1)

            # First day: only 1 crew working (other 2 sections already complete)
            day1 = DailyLog.objects.get(profile=profile, day_number=1)
            assert day1.ice_used == 195  # noqa: PLR2004 1 crew * 195

            # Should have 5 days total (section at 25 needs 5 feet)
            assert DailyLog.objects.filter(profile=profile).count() == 5  # noqa: PLR2004

        finally:
            Path(config_path).unlink()

    def test_load_config_uses_file_team_count(self):
        """Test that command uses team count from file if --teams not specified"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("28 28\n")
            f.write("7\n")  # 7 teams in file
            config_path = f.name

        try:
            # Don't specify --teams, should use 7 from file
            call_command("load_wall_config", config_path)

            profile = WallProfile.objects.get(profile_number=1)

            # With 7 teams but only 2 sections, day 1 should have only 2 crews working
            day1 = DailyLog.objects.get(profile=profile, day_number=1)
            assert day1.ice_used == 390  # noqa: PLR2004 2 crews * 195

        finally:
            Path(config_path).unlink()

    def test_load_config_resets_logs(self):
        """Test that running the command wipes old logs and starts fresh"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("28\n")  # Needs 2 days
            f.write("1\n")
            config_path = f.name

        try:
            # First run: creates 2 logs
            call_command("load_wall_config", config_path, "--teams", "1")
            assert DailyLog.objects.count() == 2  # noqa: PLR2004

            # Second run: should delete the first 2 and create 2 new ones
            call_command("load_wall_config", config_path, "--teams", "1")

            # If it accumulated, this would be 4.
            # Since it resets, it stays 2.
            assert DailyLog.objects.count() == 2  # noqa: PLR2004

        finally:
            Path(config_path).unlink()

    def test_load_config_with_zero_height_sections(self):
        """Test sections starting at height 0"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("0 0\n")  # Two sections starting at 0
            f.write("2\n")
            config_path = f.name

        try:
            call_command("load_wall_config", config_path, "--teams", "2")

            profile = WallProfile.objects.get(profile_number=1)

            # Both sections need 30 feet, should take 30 days
            logs = DailyLog.objects.filter(profile=profile)
            assert logs.count() == 30  # noqa: PLR2004

            # Each day should use 390 ice (2 crews * 195)
            for log in logs:
                assert log.ice_used == 390  # noqa: PLR2004

        finally:
            Path(config_path).unlink()


@pytest.mark.django_db
class TestCreateWallConfigCommand:
    """Tests for create_wall_config management command"""

    def test_create_default_config(self):
        """Test creating a config file with default settings"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            config_path = f.name

        try:
            Path(config_path).unlink()

            out = StringIO()
            call_command("create_wall_config", config_path, stdout=out)

            assert Path(config_path).exists()

            with Path(config_path).open() as f:
                lines = f.readlines()
                # Default is 5 profiles + 1 line for team count
                assert len(lines) == 6  # noqa: PLR2004

                # Each profile line should have 2000 sections (default)
                first_line_sections = len(lines[0].split())
                assert first_line_sections == 2000  # noqa: PLR2004

                # Last line should be the team count (default 5)
                assert lines[-1].strip() == "5"

            assert "Successfully generated" in out.getvalue()

        finally:
            if Path(config_path).exists():
                Path(config_path).unlink()

    def test_create_config_with_custom_settings(self):
        """Test creating a config file with custom profiles and sections"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            config_path = f.name

        try:
            Path(config_path).unlink()

            call_command(
                "create_wall_config",
                config_path,
                "--profiles",
                "3",
                "--sections",
                "10",
                "--teams",
                "7",
            )

            assert Path(config_path).exists()

            with Path(config_path).open() as f:
                lines = f.readlines()
                # Should have 3 profiles + 1 team count line
                assert len(lines) == 4  # noqa: PLR2004

                # Each profile line should have 10 sections
                for line in lines[:-1]:  # All lines except the last
                    sections = line.strip().split()
                    assert len(sections) == 10  # noqa: PLR2004

                    # Each height should be between 0 and 30
                    for height in sections:
                        h = int(height)
                        assert 0 <= h <= 30  # noqa: PLR2004

                # Last line should be the team count
                assert lines[-1].strip() == "7"

        finally:
            if Path(config_path).exists():
                Path(config_path).unlink()

    def test_create_config_validates_heights(self):
        """Test that generated heights are in valid range [0-30]"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            config_path = f.name

        try:
            Path(config_path).unlink()

            call_command(
                "create_wall_config",
                config_path,
                "--profiles",
                "2",
                "--sections",
                "50",
            )

            with Path(config_path).open() as f:
                for line in f:
                    heights = [int(h) for h in line.strip().split()]
                    for height in heights:
                        assert 0 <= height <= 30  # noqa: PLR2004

        finally:
            if Path(config_path).exists():
                Path(config_path).unlink()

    def test_create_config_single_profile(self):
        """Test creating config with single profile"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            config_path = f.name

        try:
            Path(config_path).unlink()

            call_command(
                "create_wall_config",
                config_path,
                "--profiles",
                "1",
                "--sections",
                "5",
            )

            with Path(config_path).open() as f:
                lines = f.readlines()
                assert len(lines) == 2  # noqa: PLR2004
                assert len(lines[0].split()) == 5  # noqa: PLR2004

        finally:
            if Path(config_path).exists():
                Path(config_path).unlink()
