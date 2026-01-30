import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.core.management.base import BaseCommand

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile

logger = logging.getLogger("crews")
ICE_PER_FOOT = 195
MAX_HEIGHT = 30
DEFAULT_TEAM_COUNT = 5


class Command(BaseCommand):
    help = "Simulates wall construction from a config file"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)
        parser.add_argument(
            "--teams",
            type=int,
            default=DEFAULT_TEAM_COUNT,
            help="Number of wall teams",
        )

    def handle(self, *args, **options):
        # 1. Clear previous simulation data
        DailyLog.objects.all().delete()
        WallProfile.objects.all().delete()

        sections_to_build = self.parse_config(options["file_path"])

        num_teams = self.num_teams_from_file
        if options["teams"] != DEFAULT_TEAM_COUNT:
            num_teams = options["teams"]

        logger.info("Starting simulation with %s teams...", num_teams)

        day = 1
        while any(s["height"] < MAX_HEIGHT for s in sections_to_build):
            # Get only sections that need work
            active_sections = sorted(
                [s for s in sections_to_build if s["height"] < MAX_HEIGHT],
                key=lambda x: x["height"],
            )

            assignments = []
            for i in range(num_teams):
                # Assign team to the next available section in the list
                section = active_sections[i] if i < len(active_sections) else None
                assignments.append((i + 1, section))

            # Dispatch work for the day
            with ThreadPoolExecutor(max_workers=num_teams) as executor:
                # Use a list to force the generator to evaluate/complete
                list(
                    executor.map(
                        lambda a, d=day: self.execute_team_job(a[0], a[1], d),
                        assignments,
                    ),
                )

            # Record total ice used by profile for THIS day
            worked_on_this_day = [a[1] for a in assignments if a[1] is not None]
            if worked_on_this_day:
                self.record_ice_usage(worked_on_this_day, day)

            day += 1

    @staticmethod
    def execute_team_job(team_id, section, day):
        if section:
            section["height"] += 1
            logger.info(
                "Day %s: Team %s worked on %s - Section %s",
                day,
                team_id,
                section["profile"].name,
                section["section_id"],
            )
        else:
            logger.info("Day %s: Team %s relieved", day, team_id)

    def parse_config(self, file_path):
        with Path(file_path).open() as f:
            # Filter out empty lines and whitespace
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            error_msg = "The config file is empty."
            raise ValueError(error_msg)

        # The last line is the number of teams
        try:
            self.num_teams_from_file = int(lines.pop())
        except ValueError:
            logger.exception("Invalid team count in config file")
            raise

        sections = []
        for i, line in enumerate(lines, 1):
            heights = [int(x) for x in line.split()]
            profile, _ = WallProfile.objects.get_or_create(
                profile_number=i,
                defaults={"name": f"Profile {i}"},
            )
            for section_idx, h in enumerate(heights):
                sections.append(
                    {
                        "profile": profile,
                        "section_id": f"{i}-{section_idx}",
                        "height": h,
                    },
                )
        # Sort so that we prioritize the first section of every profile first,
        # then the second section of every profile, etc.
        # This ensures teams spread out across profiles.
        sections.sort(key=lambda x: x["section_id"].split("-")[1])
        return sections

    @staticmethod
    def record_ice_usage(work_done_today, day):
        # We need to group the work by profile because multiple teams
        # might be working on different sections of the SAME profile.
        usage_by_profile = {}
        for section in work_done_today:
            p_id = section["profile"].id
            usage_by_profile[p_id] = usage_by_profile.get(p_id, 0) + ICE_PER_FOOT

        # Create the logs
        logs = [
            DailyLog(profile_id=p_id, day_number=day, ice_used=amount)
            for p_id, amount in usage_by_profile.items()
        ]
        DailyLog.objects.bulk_create(logs)
