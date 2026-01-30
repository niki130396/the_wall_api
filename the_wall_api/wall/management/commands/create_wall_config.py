import random
from pathlib import Path

from django.core.management.base import BaseCommand

from the_wall_api.wall.constants import MAX_HEIGHT


class Command(BaseCommand):
    help = "Generates a random wall configuration file"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str, help="Name of the file to create")
        parser.add_argument(
            "--profiles",
            type=int,
            default=5,
            help="Number of wall profiles",
        )
        parser.add_argument(
            "--sections",
            type=int,
            default=2000,
            help="Sections per profile",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        num_profiles = options["profiles"]
        num_sections = options["sections"]

        with Path.open(filename, "w") as f:
            for _ in range(num_profiles):
                # Generate random heights between 0 and MAX_HEIGHT
                # Using standard random is fine for test data generation (not crypto)
                heights = [
                    str(random.randint(0, MAX_HEIGHT))  # noqa: S311
                    for _ in range(num_sections)
                ]
                f.write(" ".join(heights) + "\n")

        self.stdout.write(self.style.SUCCESS(f"Successfully generated {filename}"))
