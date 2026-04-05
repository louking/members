# Members (Membertility) — CLAUDE.md

## Project Overview

Flask-based web application for managing club operations (primarily running clubs). Modules include leadership task tracking, meetings/e-voting, membership, awards (RunSignUp), racing team, organization, and community (Discourse) management.

## Tech Stack

- **Backend**: Python 3.12, Flask 3.0, SQLAlchemy 2.0, Flask-Security-Too, Flask-Migrate (Alembic)
- **Database**: MySQL 8.0 (two DBs: `members` for app data, `users` for authentication)
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
- `flask community ...` (Discourse group sync)

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

**Configuration**: INI-format config files in `config/`, mounted read-only in Docker. Secrets via Docker secrets (`/run/secrets/`). Environment variable overrides with `FLASK_` prefix.

**Assets**: Webassets bundles; `ASSETS_DEBUG=True` for unminified dev mode.

**Security**: Flask-Security-Too + Flask-Principal for role-based access. CSRF via Flask-WTF.

**Email**: Per-interest `from_email`; HTML+text templates; MailChimp for lists.

**Logging**: `applogging.py`; separate file/mail log levels; timezone-aware (ET).
