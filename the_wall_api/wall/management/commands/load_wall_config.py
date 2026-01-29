import logging
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from the_wall_api.wall.models import WallProfile, DailyLog


logger = logging.getLogger("crews")


class Command(BaseCommand):
    help = 'Simulates wall construction from a config file'

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)
        parser.add_argument("--teams", type=int, default=5, help="Number of wall teams")

    def handle(self, *args, **options):
        sections_to_build = self.parse_config(options['file_path'])

        num_teams = self.num_teams_from_file
        if options['teams'] != 5:  # Assuming 5 is our default argument
            num_teams = options['teams']

        logger.info(f"Starting simulation with {num_teams} teams...")

        day = 1
        while any(s['height'] < 30 for s in sections_to_build):
            active_sections = [s for s in sections_to_build if s['height'] < 30]

            # 1. Create a list of assignments for the day
            # Format: [(1, section_A), (2, section_B), (3, None)...]
            assignments = []
            for i in range(1, num_teams + 1):
                section = active_sections[i - 1] if (i - 1) < len(active_sections) else None
                assignments.append((i, section))

            # 2. Dispatch to the pool
            with ThreadPoolExecutor(max_workers=num_teams) as executor:
                # We unpack the tuple inside the mapped function
                list(executor.map(lambda a: self.execute_team_job(a[0], a[1], day), assignments))

            # 3. Record ice for sections that actually had work done
            actual_work = [a[1] for a in assignments if a[1] is not None]
            self.record_ice_usage(actual_work, day)

            day += 1

    @staticmethod
    def execute_team_job(team_id, section, day):
        """This runs inside the THREAD"""
        if section:
            section['height'] += 1
            logger.info(
                f"Day {day}: Team {team_id} worked on {section['profile'].name} - "
                f"Section {section['section_id']}"
            )
        else:
            logger.info(f"Day {day}: Team {team_id} relieved")

    def parse_config(self, file_path):
        with open(file_path, 'r') as f:
            # Filter out empty lines and whitespace
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            raise ValueError("The config file is empty.")

        # The last line is the number of teams
        try:
            self.num_teams_from_file = int(lines.pop())
        except ValueError:
            logger.error("Last line of config must be an integer for teams.")
            raise

        sections = []
        for i, line in enumerate(lines, 1):
            heights = [int(x) for x in line.split()]
            profile, _ = WallProfile.objects.get_or_create(
                profile_number=i,
                defaults={'name': f"Profile {i}"}
            )
            for section_idx, h in enumerate(heights):
                sections.append({
                    'profile': profile,
                    'section_id': f"{i}-{section_idx}",
                    'height': h
                })
        return sections

    @staticmethod
    def record_ice_usage(work_done_today, day):
        # work_done_today is a list of the sections the threads worked on
        ICE_PER_FOOT = 195

        # We need to group the work by profile because multiple teams
        # might be working on different sections of the SAME profile.
        usage_by_profile = {}
        for section in work_done_today:
            p_id = section['profile'].id
            usage_by_profile[p_id] = usage_by_profile.get(p_id, 0) + ICE_PER_FOOT

        # Create the logs
        logs = [
            DailyLog(profile_id=p_id, day_number=day, ice_used=amount)
            for p_id, amount in usage_by_profile.items()
        ]
        DailyLog.objects.bulk_create(logs)
