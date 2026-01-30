"""
Management command to load and simulate wall construction from a config file.

The command operates in two phases:
1. Ingest: Stream the config file into the database without loading everything
   into memory
2. Simulate: Process construction day-by-day, assigning teams to the shortest
   sections
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from the_wall_api.wall.constants import DEFAULT_TEAM_COUNT
from the_wall_api.wall.constants import ICE_PER_FOOT
from the_wall_api.wall.constants import MAX_HEIGHT
from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile
from the_wall_api.wall.models import WallSection

logger = logging.getLogger("crews")


class Command(BaseCommand):
    help = "Simulates wall construction using streaming for memory efficiency"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to wall configuration file",
        )
        parser.add_argument(
            "--teams",
            type=int,
            help="Number of construction teams (overrides value in config file)",
        )

    def handle(self, *args, **options):
        """Main entry point for the management command."""
        self._clear_existing_data()

        file_path = options["file_path"]
        team_count = self._load_config_file(file_path)

        # Command-line argument overrides config file value
        if options.get("teams"):
            team_count = options["teams"]

        logger.info("Starting construction simulation with %s teams", team_count)
        self._simulate_construction(team_count)

    @staticmethod
    def _clear_existing_data():
        """Remove all existing wall data from the database."""
        DailyLog.objects.all().delete()
        WallSection.objects.all().delete()
        WallProfile.objects.all().delete()

    def _load_config_file(self, file_path):
        """
        Stream config file into database without loading entire file into memory.

        Config file format:
        - Each line (except the last) contains space-separated section heights
          for a profile
        - Last line contains the number of construction teams

        Returns:
            int: Number of teams from the config file
        """
        with Path(file_path).open() as f:
            # Filter out empty lines using a generator for memory efficiency
            lines = (line.strip() for line in f if line.strip())

            # Read first line
            previous_line = next(lines, None)
            if previous_line is None:
                msg = "The config file is empty."
                raise ValueError(msg)

            # Process each line as a profile until we reach the last line (team count)
            profile_number = 1
            for current_line in lines:
                self._create_profile_with_sections(previous_line, profile_number)
                profile_number += 1
                previous_line = current_line

            # Last line should be the team count
            return self._parse_team_count(previous_line)

    @staticmethod
    def _parse_team_count(line):
        """Parse team count from the last line of the config file."""
        try:
            return int(line)
        except (ValueError, TypeError):
            logger.warning(
                "Could not parse team count from last line: '%s'. Using default: %s",
                line,
                DEFAULT_TEAM_COUNT,
            )
            return DEFAULT_TEAM_COUNT

    def _simulate_construction(self, team_count):
        """
        Simulate day-by-day construction.

        Load sections into memory, simulate using threading on in-memory data,
        then bulk-update database at the end for efficiency and thread-safety.
        """
        # Load all sections into memory as dictionaries for thread-safe manipulation
        sections = self._load_sections_into_memory()

        day = 1
        while any(s["height"] < MAX_HEIGHT for s in sections):
            # Get sections that need work, sorted by height
            active_sections = sorted(
                [s for s in sections if s["height"] < MAX_HEIGHT],
                key=lambda x: (x["height"], x["profile_number"]),
            )[:team_count]

            if not active_sections:
                break

            # Prepare assignments (team_id, section or None)
            assignments = [
                (i + 1, active_sections[i] if i < len(active_sections) else None)
                for i in range(team_count)
            ]

            # Execute work in parallel threads
            # Use a helper to avoid loop variable binding issue in lambda
            current_day = day
            with ThreadPoolExecutor(max_workers=team_count) as executor:
                list(
                    executor.map(
                        lambda assignment, d=current_day: self._execute_team_work(
                            assignment[0],
                            assignment[1],
                            d,
                        ),
                        assignments,
                    ),
                )

            # Record daily progress for sections that had work done
            worked_on = [a[1] for a in assignments if a[1] is not None]
            if worked_on:
                self._record_daily_progress(worked_on, day)

            day += 1

        logger.info("Construction complete on day %s", day - 1)

        # Bulk update all sections in the database
        self._save_sections_to_database(sections)

    @staticmethod
    def _load_sections_into_memory():
        """
        Load all wall sections from database into memory as dictionaries.

        Returns a list of dicts for thread-safe in-memory manipulation.
        """
        return [
            {
                "id": section.id,
                "profile_id": section.profile_id,
                "profile_name": section.profile.name,
                "profile_number": section.profile.profile_number,
                "section_index": section.section_index,
                "height": section.height,
            }
            for section in WallSection.objects.select_related("profile").all()
        ]

    @staticmethod
    def _execute_team_work(team_id, section, day):
        """
        Execute work for a single team on a single section.

        Modifies the in-memory section dict - no database access, so thread-safe.
        """
        if section:
            section["height"] += 1
            logger.info(
                "Day %s: Team %s worked on %s Section %s",
                day,
                team_id,
                section["profile_name"],
                section["section_index"],
            )

    @staticmethod
    def _save_sections_to_database(sections):
        """Bulk update all section heights in the database."""
        section_objects = []
        for section_data in sections:
            section = WallSection(
                id=section_data["id"],
                profile_id=section_data["profile_id"],
                section_index=section_data["section_index"],
                height=section_data["height"],
            )
            section_objects.append(section)

        WallSection.objects.bulk_update(section_objects, ["height"])

    @transaction.atomic
    def _create_profile_with_sections(self, line, profile_number):
        """
        Create a wall profile and its sections in a single database transaction.

        Args:
            line: Space-separated string of section heights (e.g., "21 25 28")
            profile_number: Sequential profile identifier
        """
        heights = [int(h) for h in line.split()]

        profile = WallProfile.objects.create(
            profile_number=profile_number,
            name=f"Profile {profile_number}",
        )

        sections = [
            WallSection(profile=profile, section_index=index, height=height)
            for index, height in enumerate(heights)
        ]
        WallSection.objects.bulk_create(sections)

    @staticmethod
    def _record_daily_progress(sections, day):
        """
        Record ice consumption for all profiles that had work done today.

        Groups sections by profile and calculates total ice used per profile.
        Creates DailyLog entries in bulk for efficiency.

        Args:
            sections: List of in-memory section dicts that had work done today
            day: Current day number
        """
        # Group ice usage by profile
        ice_usage_by_profile = {}
        for section in sections:
            profile_id = section["profile_id"]
            ice_usage_by_profile[profile_id] = (
                ice_usage_by_profile.get(profile_id, 0) + ICE_PER_FOOT
            )

        # Create daily logs for all profiles that had work done
        daily_logs = [
            DailyLog(profile_id=profile_id, day_number=day, ice_used=ice_amount)
            for profile_id, ice_amount in ice_usage_by_profile.items()
        ]
        DailyLog.objects.bulk_create(daily_logs)
