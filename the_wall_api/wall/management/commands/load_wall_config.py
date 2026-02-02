"""
Management command to load and simulate wall construction from a config file.

The command operates in two phases:
1. Ingest: Stream the config file into the database without loading everything
   into memory
2. Simulate: Process construction day-by-day, assigning teams to the shortest
   sections
"""

import io
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread

from django.core.management.base import BaseCommand
from django.db import connection
from django.db import connections
from django.db.models import F

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

    def _load_config_file(self, file_path, batch_size=100):
        """
        Stream config file into database using micro-batching for performance.

        Config file format:
        - Each line (except the last) contains space-separated section heights
          for a profile
        - Last line contains the number of construction teams

        Args:
            file_path: Path to the configuration file
            batch_size: Number of profiles to batch in a single transaction
             (default: 100)

        Returns:
            int: Number of teams from the config file
        """
        batch_queue = queue.Queue(maxsize=5)

        def worker():
            while True:
                batch = batch_queue.get()
                if batch is None:
                    break
                try:
                    self._create_profiles_batch(batch)
                finally:
                    batch_queue.task_done()

        consumer = Thread(target=worker, daemon=True)
        consumer.start()

        with Path(file_path).open() as f:
            # Filter out empty lines using a generator for memory efficiency
            lines = (line.strip() for line in f if line.strip())

            # Read first line
            previous_line = next(lines, None)
            if previous_line is None:
                msg = "The config file is empty."
                raise ValueError(msg)

            # Batch profiles for efficient bulk insertion
            profile_batch = []
            profile_number = 1

            for current_line in lines:
                profile_batch.append((previous_line, profile_number))
                profile_number += 1

                # When batch is full, insert it
                if len(profile_batch) >= batch_size:
                    batch_queue.put(profile_batch)
                    profile_batch = []

                previous_line = current_line

            # Insert any remaining profiles in the batch
            if profile_batch:
                batch_queue.put(profile_batch)

            batch_queue.put(None)
            consumer.join()

            logger.info("Ingestion complete: %s profiles total", profile_number - 1)

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
        day = 1

        # Create the pool ONCE to reuse threads and connections
        with ThreadPoolExecutor(max_workers=team_count) as executor:
            while True:
                # 1. Fetch work (Memory Efficient)
                sections_to_work_on = list(
                    WallSection.objects.filter(height__lt=MAX_HEIGHT)
                    .select_related("profile")
                    .order_by("height", "profile__profile_number")[:team_count],
                )

                if not sections_to_work_on:
                    logger.info("Construction complete on day %s", day - 1)
                    break

                work_assignments = [
                    {
                        "team_id": i + 1,
                        "section_id": section.id,
                        "profile_name": section.profile.name,
                        "section_index": section.section_index,
                        "profile_id": section.profile_id,
                    }
                    for i, section in enumerate(sections_to_work_on)
                ]

                # 2. Execute parallel updates
                # list() forces the generator to finish so we know Day X is done
                list(
                    executor.map(
                        lambda w, d=day: self._execute_team_work(w, d),
                        work_assignments,
                    ),
                )

                # 3. Bulk log (Postgres loves bulk inserts)
                self._record_daily_progress_from_assignments(work_assignments, day)
                day += 1

    @staticmethod
    def _execute_team_work(work_assignment, day):
        # Use the 'default' connection explicitly in threads
        conn = connections["default"]
        try:
            WallSection.objects.filter(id=work_assignment["section_id"]).update(
                height=F("height") + 1,
            )

            logger.info(
                "Day %s: Team %s worked on %s Section %s",
                day,
                work_assignment["team_id"],
                work_assignment["profile_name"],
                work_assignment["section_index"],
            )
        finally:
            # Important: Don't close if using a connection proxy,
            # but for standard commands, this prevents the freeze.
            conn.close()

    # @transaction.atomic
    def _create_profiles_batch(self, profile_batch):
        """
        Create multiple profiles and their sections in a single transaction.

        Uses bulk operations for maximum performance. Batching profiles reduces
        the number of database transactions from N to N/batch_size.

        Args:
            profile_batch: List of tuples (line, profile_number)
        """
        batch_start = profile_batch[0][1]
        batch_end = profile_batch[-1][1]

        logger.info(
            "Starting transaction for profiles %s-%s (%s profiles)",
            batch_start,
            batch_end,
            len(profile_batch),
        )

        # Step 1: Bulk create all profiles in the batch
        profiles_to_create = [
            WallProfile(
                profile_number=profile_number,
                name=f"Profile {profile_number}",
            )
            for line, profile_number in profile_batch
        ]
        created_profiles = WallProfile.objects.bulk_create(profiles_to_create)

        output = io.StringIO()
        section_count = 0
        for profile, (line, _) in zip(created_profiles, profile_batch, strict=True):
            heights = [int(h) for h in line.split()]
            for idx, h in enumerate(heights):
                output.write(f"{profile.id}\t{idx}\t{h}\n ")
                section_count += 1

        content = output.getvalue().strip()
        if not content:
            return

        with (
            connection.cursor() as cursor,
            cursor.copy(
                "COPY wall_wallsection (profile_id, section_index, height) FROM STDIN",
            ) as copy,
        ):
            copy.write(content)

        output.close()

        logger.info(
            "Transaction completed: Created %s profiles and %s sections",
            len(created_profiles),
            section_count,
        )

    @staticmethod
    def _record_daily_progress_from_assignments(work_assignments, day):
        """
        Record ice consumption for all profiles that had work done today.

        Groups sections by profile and calculates total ice used per profile.
        Creates DailyLog entries in bulk for efficiency.

        Args:
            work_assignments: List of work assignment dicts with profile_id
            day: Current day number
        """
        # Group ice usage by profile
        ice_usage_by_profile = {}
        for assignment in work_assignments:
            profile_id = assignment["profile_id"]
            ice_usage_by_profile[profile_id] = (
                ice_usage_by_profile.get(profile_id, 0) + ICE_PER_FOOT
            )

        # Create daily logs for all profiles that had work done
        daily_logs = [
            DailyLog(profile_id=profile_id, day_number=day, ice_used=ice_amount)
            for profile_id, ice_amount in ice_usage_by_profile.items()
        ]
        DailyLog.objects.bulk_create(daily_logs)
