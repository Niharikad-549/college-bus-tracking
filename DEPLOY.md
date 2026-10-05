# Deployment Guide: Render

This project is configured for Render with Gunicorn, WhiteNoise, secure production settings, and a hosted PostgreSQL database. The included `render.yaml` provisions a Starter web service and a Basic PostgreSQL instance; both are paid plans. Review Render's current pricing and selected plans before creating resources.

## 1. Push the repository to GitHub

Create a GitHub repository and push the project branch. Do not commit `.env`, `db.sqlite3`, or passwords. The root `.gitignore` excludes them.

```bash
git remote add origin https://github.com/<your-account>/<your-repository>.git
git push -u origin master
```

Use the branch you intend to deploy if it is not named `master`.

## 2. Create Render resources

1. In Render, choose **New + → Blueprint**.
2. Connect the GitHub repository and select the deployment branch.
3. Review the web service and PostgreSQL database from `render.yaml`.
4. Check the database plan and expected charges, then apply the Blueprint.
5. Render installs Python packages, collects static files, runs migrations in the pre-deploy command, and starts Gunicorn.

The web service uses the database's internal connection URL. The database and web service should remain in the same Render region.

## 3. Configure secrets and environment

The Blueprint generates `SECRET_KEY` and sets `DEBUG=False`. In the Render web service environment, verify or set:

- `DATABASE_URL`: supplied from the PostgreSQL resource by the Blueprint.
- `SECRET_KEY`: generated, private value. Never copy it into Git or public logs.
- `DEBUG=False`.
- `ALLOWED_HOSTS`: include your Render hostname if you use a custom value; the app also reads Render's `RENDER_EXTERNAL_HOSTNAME` automatically.
- `CSRF_TRUSTED_ORIGINS`: include the exact HTTPS origin for a custom domain, e.g. `https://buses.example.com`. The Render hostname is added automatically when `RENDER_EXTERNAL_HOSTNAME` is present.
- `SECURE_SSL_REDIRECT=True` (the production default).

For a custom domain, configure it in Render, wait for TLS provisioning, add the hostname to `ALLOWED_HOSTS`, and add its HTTPS origin to `CSRF_TRUSTED_ORIGINS`. Cookies are secure when `DEBUG=False`, and HSTS is enabled with a one-year default.

## 4. Create the first administrator

After the first successful deploy, open the Render web service Shell and run:

```bash
python manage.py createsuperuser
```

Do not use the demo credentials for a production administrator. To populate sample Vapi data in a non-production/demo instance only:

```bash
python manage.py create_demo_users
python manage.py seed_demo_data
```

Demo account passwords are documented in `README.md`; do not load demo accounts into a production system with real riders.

## 5. Verify deployment

1. Open `https://<your-render-host>/accounts/login/` and sign in with the administrator you created.
2. Visit `/dashboard/admin/` and `/dashboard/admin/live/`.
3. Add or seed a driver, bus, route, stops, and student assignment in a test environment.
4. Check `/health/`, `/api/routes/<route-id>/stops/`, and `/api/buses/<bus-id>/location/` while authenticated.
5. Confirm HTTP redirects to HTTPS and that static files load through WhiteNoise.
6. Review Render logs for migration, database, static asset, or application errors.

## 6. Test driver GPS from a phone

1. Open the deployed **HTTPS** site on the phone. Browser GPS is restricted to secure contexts; do not use the Render service over plain HTTP.
2. Sign in using a driver account assigned to a bus.
3. Open `/dashboard/driver/`, tap **Start trip**, and accept the browser's location permission prompt.
4. Keep the browser tab open and the phone awake during the test. Check that coordinates and “Last sent” update.
5. Sign in as a student assigned to the same bus route on another device or browser. The live map should update within approximately five seconds.
6. Tap **Stop trip** on the driver page. The driver page should stop sending locations.

If GPS permission was denied, enable location for the site in the phone browser settings and use **Try GPS again**. Mobile power-saving modes and background-tab suspension can pause browser GPS; test with the driver page in the foreground.

## Database options

- **Render PostgreSQL (recommended):** provided by the Blueprint through `DATABASE_URL`. Render's internal URL is preferable from the web service.
- **Hosted MySQL:** the application includes `mysqlclient` and `dj-database-url`. Set `DATABASE_URL` to the provider's MySQL URL and ensure the provider allows connections from Render. MySQL is not provisioned by the included Blueprint.
- **SQLite:** suitable for local development only. Render's application filesystem is ephemeral, so SQLite is not a durable production database.

## Operations and troubleshooting

- **Static files missing:** confirm the build command completed `collectstatic` and that WhiteNoise is enabled in middleware.
- **CSRF 403 on a custom domain:** add the full `https://` origin to `CSRF_TRUSTED_ORIGINS`; do not disable CSRF checks.
- **Database connection failure:** verify `DATABASE_URL`, database availability, region/network rules, and that migrations ran.
- **Phone GPS unavailable:** verify HTTPS, site-level location permission, and that the page is foregrounded.
- **OSRM unavailable:** ETA uses the local Haversine/25 km/h fallback; live bus positions do not depend on OSRM.
