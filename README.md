# College Bus Tracking System

A Django application for managing college buses, routes, stops, and student assignments, with driver-submitted GPS locations and live maps for students and administrators.

## Features

- Role-based accounts for administrators, drivers, and students.
- Custom admin dashboard for buses, routes, stops, drivers, and student route assignments.
- Driver trip controls and browser geolocation updates while a trip is active.
- Student live map with route stops, pickup highlighting, bus status, speed, stale-location warnings, and ETA.
- Admin live fleet map for all active trips.
- Leaflet maps with OpenStreetMap tiles and free OSRM routing; straight-line fallback is used when OSRM is unavailable.
- Location history capped at the latest 500 records per bus.
- Vapi demo dataset and a route-based bus simulator.

## Technology

- Python 3.12+
- Django 6.1 and Django REST Framework
- Django templates, HTML, CSS, and vanilla JavaScript
- Leaflet.js with OpenStreetMap tiles
- SQLite for local development; PostgreSQL or MySQL through `DATABASE_URL`
- WhiteNoise and Gunicorn for deployment

## Screenshots

Screenshots can be added here after capturing the admin dashboard, driver controls, and student live map.

- Admin dashboard: `docs/screenshots/admin-dashboard.png` (placeholder)
- Driver dashboard: `docs/screenshots/driver-dashboard.png` (placeholder)
- Student live map: `docs/screenshots/student-live-map.png` (placeholder)

## Project Structure

```text
apps/
  accounts/       Custom user, authentication, role dashboards
  tracking/       Fleet models, admin CRUD, APIs, services, commands
config/           Django settings, URL configuration, WSGI/ASGI
static/
  css/            Responsive site and dashboard styles
  js/             Driver tracking, route map, admin fleet map
templates/         Shared, account, tracking, and error templates
manage.py
requirements.txt
build.sh
render.yaml
```

## Local Setup

Requirements: Python 3.12 or newer and Git. MySQL is optional; SQLite works without a database server.

### Windows PowerShell

```powershell
git clone <your-github-repository-url>
cd collage-bus-tracking
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`: set a private `SECRET_KEY`. Keep `DB_ENGINE=sqlite` for the default local database. Apply migrations, create an administrator, load demo data, and run the server:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python manage.py migrate
python manage.py createsuperuser
python manage.py create_demo_users
python manage.py seed_demo_data
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The admin application dashboard is at `/dashboard/admin/`; the all-buses live map is at `/dashboard/admin/live/`.

### macOS/Linux

```bash
git clone <your-github-repository-url>
cd collage-bus-tracking
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Set a private `SECRET_KEY` in `.env`, then run:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py create_demo_users
python manage.py seed_demo_data
python manage.py runserver
```

### Fresh-clone verification

A fresh database starts empty. Run the commands above in order. Then verify configuration and tests:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Environment Variables

| Variable | Local default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Required | Django signing key. Keep it private and out of Git. |
| `DEBUG` | `True` in `.env.example` | Set `False` in production. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames. Render's assigned hostname is added automatically when available. |
| `CSRF_TRUSTED_ORIGINS` | Empty | Comma-separated origins including scheme, for example `https://campus.example.com`. |
| `DATABASE_URL` | Empty | Optional database URL. Supports PostgreSQL and MySQL. On Render, use the database's internal connection URL. |
| `DB_ENGINE` | `sqlite` | Local fallback selector: `sqlite` or `mysql`; ignored when `DATABASE_URL` is set. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | SQLite/local MySQL values | Optional local MySQL connection settings when `DB_ENGINE=mysql`. |
| `SECURE_SSL_REDIRECT` | Based on `DEBUG` | Redirect HTTP to HTTPS in production. |
| `SECURE_HSTS_SECONDS` | One year in production | HSTS duration; production security default. |
| `RENDER_EXTERNAL_HOSTNAME` | Empty | Render provides this for the assigned service hostname; settings add its HTTPS origin to CSRF trust. |

### Database choices

- **Local SQLite:** leave `DATABASE_URL` empty and set `DB_ENGINE=sqlite`. The ignored `db.sqlite3` file is for development only.
- **MySQL:** install/use the included `mysqlclient` driver. Either supply a `mysql://user:password@host:3306/database` `DATABASE_URL` or configure the `DB_*` variables and `DB_ENGINE=mysql`.
- **Render PostgreSQL:** recommended for deployment. Set `DATABASE_URL` to Render's internal PostgreSQL connection string. `dj-database-url` selects Django's PostgreSQL backend.
- **Hosted MySQL:** supported through `DATABASE_URL` if your host supplies a reachable MySQL URL. Render's example blueprint provisions PostgreSQL.

## Demo Credentials

The `create_demo_users` command creates these development-only accounts:

| Role | Username | Password |
| --- | --- | --- |
| Admin | `demo_admin` | `DemoAdmin123!` |
| Driver | `demo_driver` | `DemoDriver123!` |
| Student | `demo_student` | `DemoStudent123!` |

`seed_demo_data` also creates Vapi sample users:

- Drivers: `vapi_driver_1`, `vapi_driver_2` / `VapiDriver123!`
- Students: `vapi_student_01` through `vapi_student_06` / `VapiStudent123!`

Change or remove demo passwords before deploying real user data. `create_demo_users` creates ordinary role accounts; it does not replace `createsuperuser` for Django's built-in admin site.

## API Endpoints

All APIs use Django REST Framework session authentication unless noted. POST requests require CSRF tokens. Driver writes require the driver role and an assigned bus; bus reads and ETA are limited to admins, the assigned driver, or students assigned to that bus's route.

| Method | Endpoint | Access / behavior |
| --- | --- | --- |
| `GET` | `/api/routes/<route_id>/stops/` | Ordered route stops; public read. |
| `POST` | `/api/driver/trip/start/` | Driver starts a trip for their assigned bus. |
| `POST` | `/api/driver/trip/stop/` | Driver ends an active trip for their bus. |
| `POST` | `/api/driver/location/` | Driver location update; requires active trip, validates coordinates/speed, throttled to 15/minute by default. |
| `GET` | `/api/buses/<bus_id>/location/` | Latest bus location and trip status for authorized roles. |
| `GET` | `/api/buses/<bus_id>/eta/?stop_id=<stop_id>` | Authorized route stop ETA; OSRM result cached for 15 seconds, with Haversine at 25 km/h as fallback. |
| `GET` | `/api/admin/active-buses/` | Admin-only active fleet locations. |
| `GET` | `/health/` | Lightweight deployment health response. |

## Demo Data and Simulation

```bash
python manage.py seed_demo_data
python manage.py simulate_bus --route-id 1 --interval 5
```

The simulator updates the route stops repeatedly. Stop it with `Ctrl+C`; use `--once` to write one sample point and exit. Both simulated and driver-submitted locations retain no more than 500 records per bus.

Phone GPS requires a secure browser context: use `localhost` for desktop testing or HTTPS for a phone. Plain HTTP on a LAN IP may be blocked by browser geolocation permissions. See [DEPLOY.md](DEPLOY.md) for Render and phone testing.

The Render Blueprint selects a paid Starter web service and a paid Basic PostgreSQL database. Review Render's current pricing and change plans before creating those resources.

## Future Improvements

- Add automated browser tests for driver GPS permissions and live polling.
- Add alerting for stale buses and trip anomalies.
- Add route assignment history and scheduled timetables.
- Add persistent production email delivery and password reset flows.
- Add database backups, monitoring, and deployment health checks.
