import random
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generates a random wall configuration file'

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str, help='Name of the file to create')
        parser.add_argument('--profiles', type=int, default=5, help='Number of wall profiles')
        parser.add_argument('--sections', type=int, default=2000, help='Sections per profile')

    def handle(self, *args, **options):
        filename = options['filename']
        num_profiles = options['profiles']
        num_sections = options['sections']

        with open(filename, 'w') as f:
            for _ in range(num_profiles):
                # Generate random heights between 0 and 30
                heights = [str(random.randint(0, 30)) for _ in range(num_sections)]
                f.write(" ".join(heights) + "\n")

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {filename}'))
