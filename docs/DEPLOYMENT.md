# Dual-Store Takeaway Ordering System deployment guide

English | [简体中文](DEPLOYMENT.zh-CN.md) · [Back to README](../README.md)

This guide deploys this repository's PostgreSQL, FastAPI and Nginx stack with Docker Compose. It covers a new instance, verification, updates and backup. The three Vue applications share the API and database; Nginx selects the store through fixed internal host mappings.

## 1. Prepare the host and source

Use a Linux server with Git, Docker Engine, Docker Compose v2, OpenSSL and curl. Docker Desktop can run the same stack for local development on macOS or Windows; run the shell commands in a compatible POSIX shell. Run all commands from the repository root unless stated otherwise. If your Docker installation needs elevated privileges, use `sudo` consistently for Docker commands.

```bash
git clone https://github.com/JackieHe12345/dual-store-takeout-ordering-system.git
cd dual-store-takeout-ordering-system
```

The repository already contains the three production builds in `nginx/html/`. Deploying those files does not require host Python or Node.js. The backend image supplies Python 3.12. Building requires access to the image and Python package registries; the checked-in Docker configuration uses Tencent mirrors.

After changing frontend source, install a Node.js version compatible with the lockfile (`20.19+` within Node 20, or `22.12+`) and rebuild all three applications:

```bash
npm ci
npm run build
```

The build performs TypeScript checking and writes customer, staff and admin assets to their respective `nginx/html/` directories. Keep those generated files with the corresponding source revision.

## 2. Create private configuration

```bash
./scripts/bootstrap-env.sh
```

The script reads `.env.example` and creates `.env` with mode `600`. It generates an independent database password, JWT secret and three initial account passwords, and writes the database password into both `POSTGRES_PASSWORD` and `DATABASE_URL`. Password values are not printed. It refuses to overwrite an existing `.env`; retain the existing file when updating an installation.

Before starting, open `.env` in a local editor. For local verification or a host-level HTTPS reverse proxy, use:

```dotenv
NGINX_BIND_ADDRESS=127.0.0.1
NGINX_PORT=8080
```

The examples below use `http://127.0.0.1:8080`. The repository's original defaults are **`0.0.0.0:80`**, which publish HTTP on all host interfaces. Choose the intended address and port explicitly, and adjust the example URLs if you use different values.

| Setting | What to keep consistent |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL initialization values must match the connection details in `DATABASE_URL`. Inside Compose the database host is `postgres:5432`. |
| `DATABASE_URL` | Uses `postgresql+asyncpg://…`; percent-encode reserved characters if manually setting a password. The generated hexadecimal password needs no such escaping. |
| `JWT_SECRET` | Use the generated random value; production requires at least 32 characters. |
| `ADMIN_DOMAIN` | Keep `admin.localhost` with the supplied Nginx configuration. It is an internal routing value, not your public website domain. |
| `SEED_SUPER_ADMIN_PASSWORD`, `SEED_STORE_A_PASSWORD`, `SEED_STORE_B_PASSWORD` | Used only when explicitly initializing an empty business database. |

Compose explicitly sets `APP_ENV=production`, `ENABLE_COMMERCE=true` and `ENABLE_TEST_COMMERCE=false` for the backend. These Compose values take precedence over the same names in `.env`. Keep this production profile for a normal instance. Preserve `.env` privately with the installation's backup.

## 3. Start and initialize an empty instance

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
docker compose exec -T backend python -m app.seed
curl --fail http://127.0.0.1:8080/Adiandiancan/api/health
```

`--wait` waits for running/healthy services. PostgreSQL starts first; the backend runs `alembic upgrade head` before Uvicorn, and Nginx waits for backend health. A successful health response is `{"status":"ok","database":"ok"}`. If startup fails, inspect `docker compose logs --tail=100 backend postgres nginx` before retrying.

The seed command is a separate, explicit initialization step. It creates two demonstration stores, their customer/staff domain bindings, roles, three management accounts and sample menus. The CLI checks `Store`, `AdminUser`, `Category` and `Dish` first: **if any of these tables already has a row, it skips the entire initialization**. Rerunning it does not repair a partial installation, recreate removed stores or reset existing passwords. Changing a `SEED_*_PASSWORD` value also does not change an existing account's password.

| Account | Role and sign-in page | Password in `.env` |
| --- | --- | --- |
| `admin` | Super administrator: `/neibuguanli/` | `SEED_SUPER_ADMIN_PASSWORD` |
| `staff_a` | Store A administrator: `/Adianneibuguanli/` | `SEED_STORE_A_PASSWORD` |
| `staff_b` | Store B administrator: `/Bdianneibuguanli/` | `SEED_STORE_B_PASSWORD` |

Read the generated passwords with a local editor. Replace the sample store details, menu, staff configuration and operating policies through the management interfaces. Before offering delivery, confirm each store's coordinates and coordinate system, delivery radius and fee tiers; delivery remains unavailable until the location is confirmed and fees are configured.

## 4. Open and verify the five entry points

| Page | Local URL | Internal API `Host` |
| --- | --- | --- |
| Store A ordering | [Open](http://127.0.0.1:8080/Adiandiancan/) | `shop-a.localhost` |
| Store B ordering | [Open](http://127.0.0.1:8080/Bdiandiancan/) | `shop-b.localhost` |
| Store A management | [Open](http://127.0.0.1:8080/Adianneibuguanli/) | `staff-a.localhost` |
| Store B management | [Open](http://127.0.0.1:8080/Bdianneibuguanli/) | `staff-b.localhost` |
| Central administration | [Open](http://127.0.0.1:8080/neibuguanli/) | `admin.localhost` |

The root URL displays an entry notice. Use the complete paths, including their trailing slash. You do not need public DNS records for the internal `.localhost` names: Nginx sets them on the API requests it forwards. For example, `/Adiandiancan/api/menu` becomes `/api/menu` with `Host: shop-a.localhost`. Bare `/api/` requests receive `404` under the supplied Nginx configuration.

Check the public menu and capabilities:

```bash
curl --fail http://127.0.0.1:8080/Adiandiancan/api/menu
curl --fail http://127.0.0.1:8080/Bdiandiancan/api/menu
curl --fail http://127.0.0.1:8080/Adiandiancan/api/commerce/capabilities
```

For this production profile, capabilities report `enabled=true`, `is_test=false` and `payment_enabled=false`. The public menu does not require staff login. Member operations have their own store-bound sessions; management operations check JWT identity, role/permissions and store or super-admin scope.

The repository also provides an acceptance script:

```bash
docker compose exec -T backend python < scripts/verify-live.py
```

The script is passed through standard input because `scripts/` is not copied into the backend image. It checks all five pages, database health, capabilities, the two menus, management access and rejection of a Store A token through the Store B entry. It expects the original `admin`, `staff_a` and `staff_b` accounts and their matching seed passwords in the container environment. It may need adaptation after accounts or store names change. Despite its “read-only” header, it signs in and therefore updates each account's `last_login_at`; it does not create orders. Its final success marker is `LIVE_ACCEPTANCE_PASSED`.

## 5. Understand persistence and public access

| Component | Responsibility and storage |
| --- | --- |
| `postgres` | PostgreSQL 16; named volume `postgres_data` persists database files. |
| `backend` | FastAPI on container port 8000; applies Alembic migrations and writes uploaded images to `/app/media/uploads`. |
| `nginx` | The only published service; serves the three static applications and proxies their API paths. |
| `media_uploads` | Mounted writable by FastAPI and read-only by Nginx at `/usr/share/nginx/html/media/uploads`. |
| `nginx/html/` | Bind-mounted static applications and bundled menu images; Nginx serves media through `/media/`. |

The database and backend ports are not published to the host. The Compose project name defaults to `takeaway`; use a different project name and host port when running a second independent instance. Changing the project name also changes which named volumes Compose selects.

Use `docker compose stop` to pause the stack and `docker compose up -d --wait` to resume it. Ordinary `docker compose down` retains named volumes. Removing volumes, including with `down -v`, deletes persistent database/media data and is not an update procedure.

For public service, configure your own domain, DNS, TLS certificate and HTTPS reverse proxy. When that proxy runs on the Docker host, the loopback binding above is an appropriate upstream. Forward the original five application paths **and `/media/`** to it without stripping their prefixes; the inner Nginx must retain its fixed internal `Host` mappings. A proxy on another host needs a reachable, appropriately restricted bind address. The repository does not provide certificate automation or a ready-made HTTPS server block.

Completing this deployment does not connect a payment provider. Orders remain `UNPAID`, online payment remains disabled and `real_revenue_cents` remains `0`; changing a deployment setting does not implement payment initiation, callbacks or refunds.

## 6. Back up and plan recovery

Preserve the PostgreSQL database, uploaded media, private `.env` and the exact source/build revision together. Pause application writes and uploads while capturing a consistent recovery set. The following creates a private backup **outside the repository**; run each command successfully before continuing:

```bash
umask 077
mkdir -p ../takeaway-backups
chmod 700 ../takeaway-backups
takeaway_backup_dir="$(mktemp -d ../takeaway-backups/manual-XXXXXXXX)"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$takeaway_backup_dir/database.dump"
docker compose exec -T postgres pg_restore --list < "$takeaway_backup_dir/database.dump" > "$takeaway_backup_dir/database-index.txt"
docker compose exec -T backend tar -C /app/media -czf - uploads > "$takeaway_backup_dir/uploads.tar.gz"
cp .env "$takeaway_backup_dir/environment.private"
git rev-parse HEAD > "$takeaway_backup_dir/source-commit.txt"
git archive --format=tar.gz HEAD > "$takeaway_backup_dir/source.tar.gz"
tar -tzf "$takeaway_backup_dir/uploads.tar.gz" > "$takeaway_backup_dir/uploads-index.txt"
```

`git archive` captures committed `HEAD`; separately preserve any local configuration or generated-asset changes needed by the installation. Copy the completed recovery set to restricted, durable storage. Listing a PostgreSQL archive or a tar archive only checks readability, not successful recovery.

[`scripts/backup-live.sh`](../scripts/backup-live.sh) is an alternative for a matching Linux environment: it requires working noninteractive `sudo -n docker` and `sha256sum`, and writes into `backups/` inside the checkout. That directory is **not ignored by the current `.gitignore`**, and `environment.private` contains credentials. Move the backup outside the repository before staging changes. Its selected source archive omits files such as `package-lock.json` and `.env.example`; keep a complete source revision in addition to that archive.

There is no automated restore script. Rehearse recovery in a separate checkout with a distinct Compose project name, new volumes and a different loopback port. Restore the database archive into that isolated PostgreSQL instance, restore `uploads/` to its media volume with ownership writable by the backend `app` user, and supply the matching private environment. Start the matching application revision, review any migrations, then verify both menus, accounts, media and store isolation. Do not seed a recovered database. Treat a database dump plus a successful isolated restore as the recovery evidence; do not try recovery commands against the active instance first.

## 7. Update an existing instance

Before updating, record the running commit, complete a backup and review changes to migrations, dependencies, Nginx and environment settings. Preserve the existing `.env`, project name and named volumes. Resolve or preserve local source changes before updating the checkout.

For an installation tracking this repository's `main` branch:

```bash
git pull --ff-only
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T nginx nginx -t
docker compose restart nginx
curl --fail http://127.0.0.1:8080/Adiandiancan/api/health
```

Rebuild the Vue applications before restarting if frontend source changed without matching generated assets. Backend startup applies pending migrations. Restarting Nginx loads changes to its bind-mounted configuration. Repeat the public checks and appropriate account checks from section 4, then inspect both store interfaces. The seed command is not part of an ordinary update.

Returning to an older application commit does not undo a database migration. Plan rollback against the actual migration changes and, when necessary, restore the matched database/media backup into an isolated environment before switching service.

## 8. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `.env` already exists | The bootstrap script protects the existing configuration. Edit it deliberately instead of regenerating credentials. |
| Image pull or package installation fails | Check access to the configured Tencent registries/mirrors; review image sources and the Dockerfile's `PIP_INDEX_URL` for your environment. |
| Backend is unhealthy or Nginx returns `502` | Inspect backend/PostgreSQL logs for connection, production-secret or Alembic errors. Keep `DATABASE_URL` aligned with the actual database credentials. |
| Changing `POSTGRES_PASSWORD` has no effect | The official image's initialization settings do not reset an already initialized database role. Coordinate a real database password change with the connection string. |
| Menu returns `404` | Use a full store entry path; confirm first-time seeding and an enabled matching store/domain binding. |
| Management returns `401` or `403` | Check account/password, token validity, enabled state, role and the correct store or central entry. |
| Delivery is unavailable | Confirm store coordinates and coordinate system, location confirmation, radius and fee tiers. |
| Images are missing after moving an installation | Restore both bundled `nginx/html/media/` assets and the `media_uploads` volume; preserve the `/media/` proxy path. |
| API documentation is missing | Production disables FastAPI's documentation pages. The supplied Nginx configuration also does not route a bare `/docs` path. |

For application behavior, tests and the request-flow diagrams, return to the [README](../README.md).
