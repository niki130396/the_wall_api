# The Wall API

A Django REST API for tracking the construction of The Wall - managing wall profiles, daily ice consumption logs, and calculating construction costs in Gold Dragons.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

License: MIT

## Project Overview

The Wall API is a Django REST Framework application that tracks the construction of wall profiles with daily ice consumption logs. Each wall profile consists of multiple sections, and the system calculates costs based on ice usage at 1,900 Gold Dragons per cubic yard.

### Key Features

- **Wall Profile Management**: Create and manage wall profiles with unique identifiers
- **Daily Logging**: Track ice consumption for each wall profile by day
- **Cost Calculation**: Automatic cost calculation (ice used × 1,900 Gold Dragons)
- **API Endpoints**:
  - `/api/profiles/{profile_number}/days/{day_number}/` - Get daily ice usage for a specific profile
  - `/api/profiles/{profile_number}/overview/` - Get complete profile overview with total costs
  - `/api/profiles/{profile_number}/overview/{day_number}/` - Get profile overview up to a specific day
  - `/api/profiles/overview/` - Get global overview of all profiles
  - `/api/profiles/overview/{day_number}/` - Get global overview up to a specific day

### Tech Stack

- **Python 3.13**
- **Django 6.0.1**
- **Django REST Framework 3.16.1**
- **PostgreSQL** (via psycopg)
- **Redis** (for caching)
- **uv** (package management)

## Getting Started

### Prerequisites

- Python 3.13
- PostgreSQL
- Redis
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd the_wall_api
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Set up environment variables (see `.envs/.local/` for examples)

4. Run database migrations:
   ```bash
   docker-compose -f docker-compose.local.yml run --rm django python manage.py migrate
   ```

5. Create a superuser (optional):
   ```bash
   docker-compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser
   ```

6. Load initial wall data (if available):
   ```bash
   docker-compose -f docker-compose.local.yml run --rm django python manage.py load_wall_data wall_config.txt
   ```

### Running the Development Server

Start the Django development server:

```bash
docker-compose -f docker-compose.local.yml up
```

The API will be available at `http://localhost:8000/api/`

## Development

### Running Tests

Run the test suite with pytest:

```bash
docker-compose -f docker-compose.local.yml run --rm django pytest
```

### Test Coverage

Generate a coverage report:

```bash
uv run coverage run -m pytest
uv run coverage html
open htmlcov/index.html
```

### Type Checking

Run type checks with mypy:

```bash
uv run mypy the_wall_api
```

### Code Linting

The project uses Ruff for linting. Pre-commit hooks are configured to automatically check code quality:

```bash
pre-commit install
pre-commit run --all-files
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

## Project Structure

```
the_wall_api/
├── the_wall_api/
│   └── wall/              # Main wall tracking app
│       ├── models.py      # WallProfile and DailyLog models
│       ├── views.py       # API viewsets
│       ├── serializers.py # DRF serializers
│       ├── management/    # Management commands
│       └── tests/         # Test suite
├── config/                # Django settings
├── compose/               # Docker compose configurations
└── manage.py             # Django management script
```

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).
