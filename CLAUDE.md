# Members (Membertility) — CLAUDE.md

## Project Overview

Flask-based web application for managing club operations (primarily running clubs). Modules include leadership task tracking, meetings/e-voting, membership, awards (RunSignUp), racing team, organization, and community (Discourse) management.

## Tech Stack

- **Backend**: Python 3.12, Flask 3.0, SQLAlchemy 2.0, Flask-Security-Too, Flask-Migrate (Alembic)
- **Database**: MySQL 8.0 (via PyMySQL driver)
- **Frontend**: Jinja2 templates, Webassets (CSS/JS bundling), Bootstrap
- **Infrastructure**: Docker + Docker Compose, Nginx reverse proxy, Gunicorn
- **External**: Google Workspace API, MailChimp, RunSignUp API, Discourse API, Mailgun (msmtp)
- **Shared libraries**: `loutilities` (custom framework, `../loutilities`), `runtilities`

## Key Directories

```
app/src/members/          # Main application package
  __init__.py             # App factory, Flask setup, security config
  model.py                # SQLAlchemy models (~1500 lines)
  settings.py             # Config classes (Development/Production/Testing)
  views/admin/            # Admin-facing blueprints
  views/frontend/         # Member-facing blueprints
  templates/              # Jinja2 HTML templates
  static/                 # CSS, JS, images
  scripts/                # Data initialization scripts
app/src/scripts/          # Flask CLI command groups (Click)
app/src/migrations/       # Alembic migration files
config/                   # members.cfg, users.cfg (secrets redacted in repo)
web/                      # Nginx config
docs/                     # Sphinx documentation
```

## Running the Project

**Docker (standard):**
```bash
docker-compose up -d
# App at http://localhost:8002

# Development mode (live reload):
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs:
docker-compose logs -f app
```

**Key `.env` variables**: `APP_PORT=8002`, `FLASK_DEBUG`, `APP_DATABASE=members`, `DEV=1`

### Static JS Assets

JS assets are **not** served from the repo's `app/src/rrwebapp/static/js/` directory. That path is shadowed by a Docker volume mount defined in `docker-compose.yml`:

```yaml
- ${JS_COMMON_HOST}:/app/${APP_NAME}/static/js:ro
```

`JS_COMMON_HOST` is set in `.env`:
```
JS_COMMON_HOST="C:\Users\lking\Documents\Lou's Software\operational\js-common"
```

This shared `js-common` directory contains all versioned JS bundles (jQuery, DataTables, yadcf, etc.) used across multiple apps. Editing files under `static/js/` in the repo has no effect on the running container — changes must be placed in `js-common`.

The yadcf development repo lives at `C:\Users\lking\Documents\Lou's Software\projects\yadcf\yadcf\`. After editing yadcf there, the built file must be copied into `js-common` under the appropriate versioned directory (e.g., `js/yadcf-<version>/`) for it to be picked up by the app.

## Database Migrations

```bash
flask db upgrade    # Apply migrations
flask db migrate    # Generate new migration
```

Docker entrypoint (`dbupgrade_and_run.sh`) runs migrations automatically on startup.

## CLI Commands

Four Click command groups, run as `flask <group> <command>`:
- `flask members ...`
- `flask membership ...` (MailChimp sync, etc.)
- `flask task ...`
- `flask community ...` (Discourse group sync, taxonomy export, event import)
  - `syncrace INTEREST RACEID GROUP` — sync group from RunSignUp race participants
  - `syncclub INTEREST CLUBID GROUP` — sync group from RunSignUp club members
  - `synctag INTEREST TAG GROUP` — sync group from internal position tag
  - `export-taxonomy INTEREST [--output FILE] [--json]` — export forum taxonomy/config to .docx (logic in `members/community_taxonomy.py`)
  - `import-events INTEREST --category-id INT [--csv-file FILE] [--state-file FILE] [--post-as USERNAME] [--dry-run]` — create one Discourse topic per row from a CSV exported by `app/src/scripts/export_fsrc_events.py`; idempotent (state tracked in `fsrc_import_state.json`); topics include discourse-calendar `[event]` BBCode so they appear in the ICS feed; logic in `members/community_events.py`. `--post-as` overrides `DISCOURSE_API_EVENT_USERNAME_<INTEREST>` for the run (which itself falls back to `DISCOURSE_API_INVITE_USERNAME_<INTEREST>` if unset)

**Calendar web route**: a single on-demand feed is served at `/<interest>/calendars/events.ics` by the Flask app (`views/frontend/community_calendar_views.py`), not as Nginx static files and not via cron. The `<interest>` URL segment is handled by the standard `pull_interest` preprocessor. Uses the `/discourse-post-event/events` JSON API (not the ICS feed) so topic tags are available inline — no per-topic API calls needed. Query params: `tags=<tag>[,<tag>...]` (optional; event included if it carries any one of the listed tags — union/OR; omitted means all events, unfiltered), `year=YYYY`, or `from=YYYY-MM-DD` (also accepts the literal `today`) / `to=YYYY-MM-DD`. If `to` is omitted, the window is open-ended (all future events) rather than capped. Compiled ICS bytes are cached per `(interest, tags, from_date, to_date)` tuple (15-minute TTL). Filtering is by raw Discourse tag slug passed directly via `tags=` — there is no config-driven series-name mapping (the old `CALENDAR_TAG_GROUPS_<INTEREST>` config key and the disk-writing `filter-calendar` CLI command were removed as dead code once this on-demand route existed; nothing else in the repo referenced them — no cron entry, no Nginx static-file serving).

## Tests

No test suite in the main app. `loutilities` has tests:
```bash
cd ../loutilities
python -m pytest tests/
```

Set `TESTING: True` in `config/members.cfg` to disable email sending during manual testing.

## Key Patterns

**Multi-tenancy**: URL structure `/app/<interest>/admin/...`; interest stored in Flask `g` via URL preprocessor; use `localinterest()` helper in views.

**Blueprints**: Admin views (`views/admin/`) vs. member-facing views (`views/frontend/`).

**Configuration**: INI-format config files in `config/`, mounted read-only in Docker. Secrets via Docker secrets (`/run/secrets/`). Environment variable overrides with `FLASK_` prefix. Values are processed through `eval()` by `loutilities.configparser.getitems`, so Python literals (booleans, ints, dicts, lists) arrive as their native types — not strings.

**Assets**: Webassets bundles; `ASSETS_DEBUG=True` for unminified dev mode.

**Security**: Flask-Security-Too + Flask-Principal for role-based access. CSRF via Flask-WTF.

**Email**: Per-interest `from_email`; HTML+text templates; MailChimp for lists.

**Logging**: `applogging.py`; separate file/mail log levels; timezone-aware (ET).

## Deployment
Uses Fabric (`fabfile.py`) for remote deployment via docker compose pull + up.

## Discourse Config Keys

Community commands look up per-interest Discourse credentials using uppercased interest names:

```python
current_app.config[f'DISCOURSE_API_URL_{uinterest}']                    # base URL
current_app.config[f'DISCOURSE_API_KEY_{uinterest}']                    # API key
current_app.config[f'DISCOURSE_API_INVITE_USERNAME_{uinterest}']        # API username for group invites/sync (must be an admin account)
current_app.config.get(f'DISCOURSE_API_EVENT_USERNAME_{uinterest}')     # optional: username for creating event topics (falls back to INVITE_USERNAME)
current_app.config.get(f'DISCOURSE_API_CALENDAR_USERNAME_{uinterest}')  # optional: username for reading the calendar feed, e.g. a low-privilege account for a public-equivalent view (falls back to INVITE_USERNAME)
current_app.config.get(f'DISCOURSE_API_CATEGORY_GROUPS_QUERY_{uinterest}')  # optional: Data Explorer query ID for category group permissions
```

The Discourse API key is configured as **"All Users"** scope in the Discourse admin panel — the key itself has no fixed permission level. Effective permissions come from the `Api-Username` header (set from `DISCOURSE_API_INVITE_USERNAME_<INTEREST>`). That username must belong to a Discourse admin account for admin API endpoints (site settings, user fields, badges, themes, etc.) to work.

## Community Module Patterns

**Rate-limited Discourse client**: All Discourse API calls must go through the rate-limited fluent_discourse client — never a raw `requests.Session`. Use `make_discourse_client(interest)` from `members/community.py`; it returns a `_RateLimitedDiscourse`-wrapped client configured from the standard `DISCOURSE_API_*` config keys at 55 calls / 60 s. Pass `username=` to override `DISCOURSE_API_INVITE_USERNAME_{INTEREST}` when you need topics/posts (or reads) done as a different account — use `DISCOURSE_API_EVENT_USERNAME_{INTEREST}` for a dedicated event-posting account and `DISCOURSE_API_CALENDAR_USERNAME_{INTEREST}` for the calendar feed's read account; the same API key is used for all of these, so override accounts don't need their own key. There is no anonymous/unauthenticated mode in this client — `Api-Key`/`Api-Username` headers are always sent, so a "public" view means authenticating as a real, low-privilege Discourse account (member of no restricted groups) rather than the admin `INVITE_USERNAME`, not a true unauthenticated request.

**Process lock**: Community commands that should not run concurrently (e.g. group sync) acquire a `fasteners.InterProcessLock` at the start and release it on completion, preventing cron overlap.

## fluent_discourse API Note

The `fluent_discourse` client uses a fluent/chained builder. HTTP verb methods (`get`, `post`, `put`, `delete`) each take a **single positional dict argument** — not keyword arguments:

```python
# CORRECT — positional dict becomes query params for GET, body for POST
client.groups._('my-group').members.json.get({'offset': 0, 'filter': ''})
client.admin.plugins.explorer.queries._(id).run.post({'params': {...}})

# WRONG — raises TypeError
client.some.endpoint.get(params={'offset': 0})
```

For `get()`, the dict is forwarded as `requests` query params. For `post()`/`put()`/`delete()`, it is sent as JSON body.

## Discourse API Quirks

- **Boolean params must be lowercase strings.** `requests` serializes Python `True` as `"True"` (capital T), but Discourse checks for `"true"`. Pass `'true'`/`'false'` strings explicitly, e.g. `{'include_subcategories': 'true'}`.
- **`GET /admin/site_settings.json` returns a list, not a flat dict.** Response is `{"site_settings": [{"setting": "key", "humanized_name": "...", "value": "...", ...}, ...]}`. Convert with `{item['setting']: {'value': item['value'], 'label': item['humanized_name']} for item in data['site_settings']}` before lookups.
- **Tags are always returned as objects, not strings, on this instance.** Both `GET /t/{id}.json` and `GET /discourse-post-event/events` return tags as `[{"id": 20, "name": "grand-prix", "slug": "grand-prix"}, ...]` — never plain strings. Always extract `t['name']` before comparing. `_tag_names()` in `community_calendar.py` normalises both forms defensively.
- **`GET /tags.json` uses `name` (not `id`) for the tag slug.** Each entry in `response['tags']` has a `name` field containing the slug string. There is also an `id` field but it is not the slug — use `t['name']` when building a set of known tag slugs.
- **discourse-calendar `[event]` block supports `url` and `location` parameters.** `url` makes the event title a clickable link in the calendar popover; `location` shows the venue. Both are set in `community_events._build_topic_body()`. Example: `[event start="2026-01-10T09:00:00" end="2026-01-10T11:30:00" status="public" timezone="America/New_York" url="https://runsignup.com/..." location="Venue, City, MD"][/event]`
- **`/discourse-post-event/events.ics` only includes future (non-expired) events.** Once an event's end time passes, Discourse marks it "Expired" and removes it from the feed. Historical events cannot be retrieved via this endpoint; calendar clients retain past events from their own cache after they sync.
- **`/discourse-post-event/events` (JSON) is what `community_calendar.py` uses for tag-filtered calendars.** Supports `after`/`before` date range params, returns past events, and includes `post.topic.tags` inline — no per-topic lookups needed. fluent_discourse path: `discourse._('discourse-post-event').events.get({'after': '...', 'before': '...', 'include_ongoing': 'true'})`. No server-side pagination metadata is exposed; a single call with a 1–2 year window returns all events in range. **`/discourse-post-event/events/{id}` does not exist** on this instance — to get event `location`, use `discourse.posts._(post_id).json.get({})` (`event['post']['id']`) and parse `response['raw']` for `[event location="..."]` with a regex. Do NOT use `/t/{topic_id}.json` for this — the `raw` field is not reliably present in the topic endpoint response. Also: `starts_at`/`ends_at` strings sometimes carry a UTC offset (`-05:00`); always call `.astimezone(ZoneInfo(tz_name))` after parsing so icalendar serialises `TZID=America/New_York` rather than `TZID="UTC-05:00"`.
- **`group_permissions` is not returned by any Discourse category API endpoint** on the FSRC instance (neither `/categories.json` nor `/categories/{id}.json`), even with an admin username. Category group permissions are fetched instead via a Discourse Data Explorer SQL query (`DISCOURSE_API_CATEGORY_GROUPS_QUERY_{INTEREST}`) that queries the `category_groups` table joined with `categories` and `groups`. The query must return columns `category_id`, `group_name`, `permission_type`. Falls back to displaying "Restricted" if the config key is absent.

## MySQL SSL / Driver Note

**Problem:** MySQL 8.0+ in Docker with Alpine-based app containers causes `MySQLdb.OperationalError: (2026, 'TLS/SSL error: Certificate verification failure')`. Alpine uses MariaDB Connector/C (not libmysqlclient), which defaults to SSL with cert verification. MySQL 8.0 auto-generates self-signed certs. Server-side workarounds (`--skip-ssl`) are unreliable in 8.0.40+.

**Fix:** Use **PyMySQL** instead of mysqlclient. PyMySQL is pure Python, does not use MariaDB Connector/C, and does not attempt SSL by default.

Three files to change:

1. **`app/requirements.txt`** — remove `mysqlclient==x.x.x` and add
   `PyMySQL==1.1.3`. Also remove `typed_ast` if present — it does not build on
   Python 3.12 and is no longer needed (its functionality is in the standard
   `ast` module).

2. **`app/src/<appname>/settings.py`** — change URI scheme in `RealDb.__init__`:
   ```python
   # before
   db_uri = f'mysql://{dbuser}:{password}@{dbserver}/{dbname}'
   # after
   db_uri = f'mysql+pymysql://{dbuser}:{password}@{dbserver}/{dbname}'
   ```
   Same change for `usersdb_uri` if present.

3. **`app/Dockerfile`** — remove the C build scaffolding for mysqlclient (PyMySQL needs no compilation):
   ```dockerfile
   # remove these lines:
   RUN apk add --no-cache mariadb-connector-c-dev \
       && apk add --no-cache --virtual .build-deps build-base mariadb-dev \
       && pip install -r requirements.txt \
       && rm -rf .cache/pip \
       && apk del .build-deps
   # replace with:
   RUN pip install -r requirements.txt \
       && rm -rf .cache/pip
   ```
   Keep `apk add --no-cache mysql-client` — the startup script and cron backup jobs use the `mariadb`/`mariadb-dump` CLI.

4. **`app/client.my.cnf`** — must exist with `ssl = false` to suppress SSL for CLI tools (`mariadb`, `mariadb-dump`). The Dockerfile copies it to `/home/appuser/.my.cnf`:
   ```ini
   # see https://stackoverflow.com/a/78683658
   [client]
   ssl = false
   ```
   And in the Dockerfile:
   ```dockerfile
   COPY client.my.cnf /home/appuser/.my.cnf
   ```
