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
config/                   # members.cfg, users.cfg (secrets redacted in repo); cronjobs (gitignored, per-environment -- see Cron Job Mail Notes)
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
  - `notify-pending-reviews INTEREST --category-slug SLUG [--category-slug SLUG ...] [--pending-hours 2.0] [--escalation-hours 24.0] [--post-as USERNAME] [--dry-run] [--debug]` — polls the Admin API review queue (`GET /review.json`) for the given categories and sends a Discourse PM to each category's configured moderator group(s). Not event-specific: it surfaces whatever is pending in the category — flagged posts, new-user posts awaiting approval, queued topics, event topics, etc. — since an "event" is just an ordinary post/topic with `[event]` BBCode, not a distinct reviewable type; Discourse's review queue has no way to filter by that anyway. Exists because Discourse's own per-category posting-review settings only show an on-site badge to non-staff moderators — they never notify them. Moderator group(s) per category come from Discourse itself, not from local config, so group changes made in Discourse admin take effect automatically — but **not** from a `reviewable_by_group_name`-style field on `GET /categories.json` as the "category-group-moderation" feature name might suggest (that field doesn't exist on this Discourse version). Confirmed live: `GET /c/{id}/show.json`'s `category.topic_posting_review_group_ids` and `category.reply_posting_review_group_ids` (both arrays of group ids, set independently for new topics vs. replies — a category can have more than one moderator group, e.g. FSRC's `public-calendar-events` category has both `club-mods` and `cal-mods`), unioned and resolved to names via `GET /groups.json`. `--category-slug` resolves through `GET /categories.json` first to get the numeric id `/c/{id}/show.json` needs. State (which reviewable IDs have already been notified on, and when) is tracked in the `discoursereviewnotice` DB table, scoped by interest — items pending less than `--pending-hours` are ignored, a first notice goes out once an item crosses that threshold, and it re-notifies (escalates) every `--escalation-hours` thereafter until the item leaves the pending queue (at which point the tracking row is deleted). Notification delivery is a swappable `notify_fn` (default `community_review.send_group_pm`, a Discourse PM) so email/webhook delivery can be added later without touching the polling/escalation logic. The PM is sent as `DISCOURSE_API_REVIEW_USERNAME_<INTEREST>` if set (`--post-as` overrides it for the run), otherwise it falls back to `DISCOURSE_API_INVITE_USERNAME_<INTEREST>` — same override-chain pattern as `import-events`'s `DISCOURSE_API_EVENT_USERNAME_<INTEREST>` and the calendar feed's `DISCOURSE_API_CALENDAR_USERNAME_<INTEREST>`. **Prints nothing on a routine run with nothing to report** (no new/escalated/resolved items, no errors) — deliberate, so a frequent cron cadence doesn't generate mail every run; pass `--debug` to always print a summary. Logic in `members/community_review.py`. Intended to run every 15 min via cron, e.g. `*/15 * * * * test "$PROD" && cd /app && flask community notify-pending-reviews fsrc --category-slug public-calendar-events`.

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

**Disabled DataTables button tooltips**: a button rendered with `{'extend': 'create', 'enabled': False, 'attr': {'title': '...'}}` (e.g. `MotionsView.setbuttons()` in `meetings_admin.py`, disabling "New" until invites are sent) gets the `title` attribute on the DOM node, but jquery-ui's `.ui-state-disabled { pointer-events: none; }` (in `jquery-ui.structure.css`, part of the `admin_css` bundle) blocks the hover event needed to show it — the tooltip silently never appears even though the markup is correct. Fixed with a `.dt-button.ui-state-disabled { pointer-events: auto; }` override in `static/admin/style.css`, which loads last in the `admin_css` bundle (`assets.py`) so it wins the cascade. Safe to override: DataTables Buttons enforces the disabled state in JS by checking `!button.hasClass(dom.disabled)` before firing click/keypress actions (`_buildButton` in `datatables.js`) — it never relied on `pointer-events: none` for that, so restoring hover doesn't make the button clickable again.

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
current_app.config.get(f'DISCOURSE_API_REVIEW_USERNAME_{uinterest}')    # optional: username for sending pending-review PMs (falls back to INVITE_USERNAME)
current_app.config.get(f'DISCOURSE_API_CATEGORY_GROUPS_QUERY_{uinterest}')  # optional: Data Explorer query ID for category group permissions
current_app.config.get(f'DISCOURSE_API_EVENT_LOCATIONS_QUERY_{uinterest}')  # optional: Data Explorer query ID for bulk event-location lookup (calendar feed)
```

The Discourse API key is configured as **"All Users"** scope in the Discourse admin panel — the key itself has no fixed permission level. Effective permissions come from the `Api-Username` header (set from `DISCOURSE_API_INVITE_USERNAME_<INTEREST>`). That username must belong to a Discourse admin account for admin API endpoints (site settings, user fields, badges, themes, etc.) to work.

The `..._QUERY_<INTEREST>` keys above reference Discourse Data Explorer queries, which live only in that Discourse instance's admin panel (Discourse has no API to create/update a query, only to run one by id). `app/src/members/discourse_data_explorer_queries.sql` is a git-tracked record of what each one is supposed to contain — update it alongside any admin-panel edit, since nothing enforces the two staying in sync.

## Community Module Patterns

**Rate-limited Discourse client**: All Discourse API calls must go through the rate-limited fluent_discourse client — never a raw `requests.Session`. Use `make_discourse_client(interest)` from `members/community.py`; it returns a `_RateLimitedDiscourse`-wrapped client configured from the standard `DISCOURSE_API_*` config keys, paced by `DISCOURSE_RATE_LIMIT_MAX_CALLS`/`_WINDOW_SECS` (`community.py`, currently 55 calls / 60 s — a 5-call margin below Discourse's confirmed default `max_admin_api_reqs_per_minute = 60` (`config/discourse_defaults.conf`), see the tuning note below). `community_taxonomy.fetch_all()` builds its own `_RateLimitedDiscourse` directly rather than via `make_discourse_client()`, but imports these same constants rather than hardcoding its own, so the two don't drift. Pass `username=` to override `DISCOURSE_API_INVITE_USERNAME_{INTEREST}` when you need topics/posts (or reads) done as a different account — use `DISCOURSE_API_EVENT_USERNAME_{INTEREST}` for a dedicated event-posting account and `DISCOURSE_API_CALENDAR_USERNAME_{INTEREST}` for the calendar feed's read account; the same API key is used for all of these, so override accounts don't need their own key. There is no anonymous/unauthenticated mode in this client — `Api-Key`/`Api-Username` headers are always sent, so a "public" view means authenticating as a real, low-privilege Discourse account (member of no restricted groups) rather than the admin `INVITE_USERNAME`, not a true unauthenticated request.

**`_RateLimiter`'s call history is shared across processes, not per-process in-memory.** An earlier, purely in-memory version only protected a single process from exceeding the budget within its own lifetime — it couldn't stop two sequential-but-close community commands from together exceeding Discourse's real server-side limit (which is enforced per API key/account, across every caller, not per local process). Confirmed live: command B starting right after command A finished got a fresh, empty in-memory limiter with no memory of A's calls from moments earlier, assumed a full budget, and hit Discourse's actual 429 (`fluent_discourse`'s own `"Discourse rate limit hit, trying again in N seconds"` retry — that message is the real server-side limit being hit, not `_RateLimiter`). Fixed by persisting recent call timestamps (wall-clock `time.time()`, not `time.monotonic()`, since they must be comparable across separate process invocations) to a state file, read-pruned-and-rewritten on every `acquire()` under its own dedicated lockfile (a short per-call critical section — separate from `COMMUNITY_LOCKFILE` below, which some but not all community commands hold for their whole duration).

**These lock/state files live on a shared Docker volume (`community-locks`), not `/tmp`** — `app` (web requests, e.g. `calendar_feed()`) and `crond` (cron-fired CLI commands) are **separate containers with separate filesystems** (`docker-compose.yml`), both built from the same image but never sharing `/tmp`. An initial version of the cross-process fix above put these files under `/tmp` and was verified working live — but every verification happened via `docker exec` into the `app` container alone, so it only ever proved coordination *within* one container, never across the `app`/`crond` boundary. That gap was the actual root cause of a real 429 that occurred despite the "confirmed working" fix: a `calendar_feed()` request in `app` and two cron-fired `notify-pending-reviews` runs in `crond` were each reading/writing their own container-local `/tmp`, invisible to each other. Fixed by mounting a new named volume at `/locks` in both `app` and `crond` in `docker-compose.yml`, and pointing `COMMUNITY_LOCKFILE`/`_RATE_LIMIT_STATE_FILE`/`_RATE_LIMIT_STATE_LOCKFILE` there instead. **Lesson for next time**: when verifying anything that's supposed to coordinate across services, check it from *every* service involved, not just the one `docker exec` happens to be convenient for.

**A fresh Docker named volume is owned `root:root`, not `appuser`, which broke this the first time.** Both `app`'s gunicorn process and `crond`'s actual cron-job executions (via `/etc/crontabs/appuser` — `crond`'s *container* defaults to `user: root`, but that's only the crond daemon itself; jobs run as the crontab's owner) run as `appuser`, and a fresh named volume mounted over `/locks` initially got `root:root` / mode `755` from Docker's default, silently blocking every write with a permission error `_RateLimiter.acquire()` never surfaced as a visible crash (writes happened inside the `with InterProcessLock(...):` block, and testing at the time happened to run as root via a bare `docker exec` into `crond`, which defaults to root and so didn't hit the permission error — masking the bug until tested as `appuser` explicitly). Fixed two ways: the Dockerfile now does `RUN mkdir -p /locks && chown appuser:appuser /locks` before `USER appuser`, so any *fresh* volume (e.g. production's, not yet created) inherits correct ownership the first time Docker copies the image's mount-path content into it — but this doesn't retroactively fix a volume that already exists, so the dev volume needed a one-time manual `docker exec <crond-container> chown -R appuser:appuser /locks` (run as root) to pick up the code without a rebuild.

**`DISCOURSE_RATE_LIMIT_MAX_CALLS` was briefly dropped to 40, then reverted to 55** after the `/tmp`-not-actually-shared issue above was found — the real 429 wasn't evidence that 55 is too close to the confirmed 60/minute limit for steady single-threaded use, it was two containers never having coordinated in the first place. Don't reflexively lower this again for a burst; see the tuning note below.

**Process lock**: Community commands that should not run concurrently (e.g. group sync, pending-review notifications) acquire a `fasteners.InterProcessLock` at the start and release it on completion, preventing cron overlap — a distinct concern from the rate-limiter sharing above (which `_RateLimiter` now handles on its own regardless of whether a given command also holds this lock), still needed even with that fix because it prevents concurrent runs from racing on *business state*, not just API budget. Two flavors of that race: `CommunitySyncManager` (`syncrace`/`syncclub`/`synctag`) reads a full snapshot of users/group-members/invites at the start and computes add/remove decisions from it — two overlapping runs each working from their own stale snapshot is a lost-update race (run A reads an invite with `group_ids=[1,2]`, adds group 3, writes `[1,2,3]`; concurrently run B read the same invite before A's write, adds group 4, writes `[1,2,4]` — group 3 silently vanishes). `community_review.check_pending_reviews()` has the same shape of problem: two overlapping runs could both see a reviewable as "not yet tracked" (neither has committed a `DiscourseReviewNotice` row yet) and both send a PM for it — a duplicate notification, not a rate-limit problem. All community commands share **one** lockfile, `COMMUNITY_LOCKFILE` (`community.py`, `/locks/communitygroupmanager.lock` on the `community-locks` volume) — deliberately, not a per-command lockfile — kept simple rather than reasoning per-pair-of-commands about which ones could actually race each other. `CommunitySyncManager.start_import()` acquires/releases it manually; `community_review.check_pending_reviews()` wraps its whole body in `with InterProcessLock(COMMUNITY_LOCKFILE):`.

**`community_calendar_views.calendar_feed()` deliberately does *not* hold `COMMUNITY_LOCKFILE`**, despite also calling Discourse through `make_discourse_client()` — considered and rejected. It already gets the rate-limit-budget sharing above for free (that's caller-agnostic, not tied to holding this lock), and it has no business-state-mutation race to guard against: it's pure read-and-cache (never writes to Discourse groups/invites or `DiscourseReviewNotice`). Holding the lock would instead add real latency for external calendar clients polling `events.ics` — a web request would block for the full duration of any in-progress community command, including that command's own rate-limit throttle sleeps (which can run 40+ seconds) — for no corresponding safety benefit.

## Discourse Rate Limit Tuning Note

Discourse's admin API key limit is confirmed, not assumed: `max_admin_api_reqs_per_minute = 60` in [`config/discourse_defaults.conf`](https://github.com/discourse/discourse/blob/main/config/discourse_defaults.conf) (this instance hasn't overridden it — the setting doesn't even appear in `GET /admin/site_settings.json`'s response, so there's no per-site value to check against; only user-facing limits like `rate_limit_create_post` are exposed there). Per the [Meta thread on this setting](https://meta.discourse.org/t/available-settings-for-global-rate-limits-and-throttling/78612), the 60/minute budget is **shared across every admin API key on the instance, not scoped to our one key** — so any *other* admin-scoped integration on this Discourse (not just our own community commands' burst behavior) would silently eat into the same budget with zero visibility to our own bookkeeping, which only tracks calls this app made. `DISCOURSE_RATE_LIMIT_MAX_CALLS`/`_WINDOW_SECS` (`community.py`) is `55`/`60` — a 5-call margin below that confirmed 60/minute, which has worked fine for steady single-threaded use. Changing the real limit itself would mean editing Discourse's own `app.yml` (`DISCOURSE_MAX_ADMIN_API_REQS_PER_MINUTE`) and rebuilding that container — out of scope for this app, and not something to reach for over an occasional rare-burst 429.

**If a real 429 recurs, don't reflexively tighten this further** — check first whether it's a *burst* problem (multiple community commands, or a command overlapping a `calendar_feed()` web request, landing at nearly the same moment — e.g. two cron lines firing in the same minute) rather than steady-state throughput being too high. Permanently lowering the ceiling taxes every normal run to guard against a rare pile-up; fixing the burst at the source (consolidating same-minute cron lines into one multi-value invocation, staggering cron minutes, etc.) is the more targeted fix. This was tried the other way once already: dropped to 40 after a burst-triggered 429, then reverted back to 55 once it was clear the burst — not the steady-state margin — was the actual cause.

## Cron Job Mail Notes

**The real crontab lives at `config/cronjobs` (gitignored, like `members.cfg`'s secrets), not in git** — mounted read-write into both `app` and `crond` containers at `/etc/crontabs/appuser` via `docker-compose.yml`. It's per-environment, hand-maintained directly on each host; this repo's own copy is normally empty in dev, since dev's Discourse/mail config in `members.cfg` points at real production endpoints and running these jobs locally would act on production data.

**A cron job's routine DEBUG-level log chatter gets mailed even when the job has nothing to report, unless its output is explicitly redirected.** Root-caused live: `notify-pending-reviews` is deliberately designed to print nothing on a routine run (see its CLI Commands entry above) specifically so a 15-minute cron cadence doesn't spam mail — but an email still arrived containing only `_RateLimiter.acquire(): throttling ...` DEBUG lines, no actual report content. Cause: the crontab's `MAILTO=webmaster@steeplechasers.org` (set at the top of `config/cronjobs`) makes cron mail the raw stdout/stderr of *any* job that produces output, completely independent of the app's own notify-only-when-relevant logic. That DEBUG chatter reaches stdout/stderr because `loutilities.user.applogging.setlogging()` unconditionally does `current_app.logger.setLevel(logging.DEBUG)` and never attaches an explicit console handler — so a Flask CLI invocation falls back to Flask's own permissive default stream handler, which passes through whatever the DEBUG-enabled logger allows. **This is not gated by `LOGGING_LEVEL_MAIL`** (`members.cfg` sets it to `50`/CRITICAL, correctly keeping the app's own `SMTPHandler` quiet) — that setting only governs the app's structured mail-alert path, not cron's independent mailing of console output. Any cron-invoked command that goes through the shared rate-limited Discourse client (`make_discourse_client`) — not just `notify-pending-reviews`, but `synctag`/`syncclub`/`syncrace` too — emits this same `_RateLimiter.acquire()` chatter whenever the shared 55-call/60s budget is contended, which is likely for the community jobs since all five fire at the same `00 */4 * * *` moment.

**Fixed at the crontab, not in code**, since lowering the shared `loutilities` logger's level would affect every app built on it, and would also quiet the file/console DEBUG detail that's been genuinely useful for troubleshooting via `docker-compose logs -f app`. Each affected line now captures output to a per-job scratch file and only echoes it back (triggering cron's normal mail) on non-zero exit:
```
*/15 * * * * cd /app && flask community notify-pending-reviews fsrc --category-slug public-calendar-events > /tmp/npr-calendar.log 2>&1 || cat /tmp/npr-calendar.log
```
This preserves real failure visibility (`catch_errors` in `scripts/__init__.py` calls `exit(1)` on `ParameterError`/`RuntimeError`; any other uncaught exception also exits non-zero by default) while eliminating routine noise. Applied to both `notify-pending-reviews` lines and the five community `synctag`/`syncclub` lines; the two `syncrace` lines are already commented out so weren't touched. Non-Discourse cron jobs (`meetings`, `task`, `membership`) were left out of scope — not yet confirmed whether they have the same issue.

**While editing, also removed vestigial `test "$PROD"`/`test "$DEV"` guards from most lines** — a holdover from when `config/cronjobs` was still a single shared file in git; now that it's per-environment, those guards are redundant (each environment already gets its own tailored file). The one exception: the leadership-emails job's `test \`expr \`date +\%s\` / 86400 \% 2\`` is a genuine even/odd-Monday date-parity check, not an environment guard, and was left alone. The `*/30 * * * *` dev-cadence db-backup line was commented out rather than left unguarded, since removing its guard would otherwise leave *two* backup schedules running unconditionally together.

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
- **`/discourse-post-event/events` (JSON) is what `community_calendar.py` uses for tag-filtered calendars.** Supports `after`/`before` date range params, returns past events, and includes `post.topic.tags` inline — no per-topic lookups needed. fluent_discourse path: `discourse._('discourse-post-event').events.get({'after': '...', 'before': '...', 'include_ongoing': 'true'})`. No server-side pagination metadata is exposed; a single call with a 1–2 year window returns all events in range. **`/discourse-post-event/events/{id}` does not exist** on this instance — event `location` isn't in the events-API payload either, so it has to come from each post's raw content (`response['raw']`, parsed for `[event location="..."]` with a regex), and `/t/{topic_id}.json` won't work for that — the `raw` field is not reliably present in the topic endpoint response, only `/posts/{id}.json` (`discourse.posts._(post_id).json.get({})`). Fetching that per-post is itself an N+1 the events-API call was supposed to have eliminated (just for `location` instead of `tags`), so `community_calendar.fetch_event_locations()` resolves it in bulk instead via a paged Data Explorer query (`DISCOURSE_API_EVENT_LOCATIONS_QUERY_{INTEREST}`, optional — falls back to the one-REST-call-per-post approach if unset) rather than caching per-post results, since an operator correcting a wrong location in the topic should see the fix on the next 15-minute `_ics_cache` rebuild, not get a stale cached value. The query takes an `int_list :post_ids` Data Explorer param (confirmed supported) and returns `id, raw` for `posts.id IN (:post_ids)`; it must also declare `:page_size`/`:page_num` int params with a `LIMIT :page_size OFFSET (:page_num * :page_size)` clause to match the paging convention shared with the other Data Explorer queries in this codebase (`community.run_query_paged()`, generalized off what was originally a `CommunitySyncManager`-only method — also used by `DISCOURSE_API_INVITES_QUERY_FSRC`, `DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC`, `DISCOURSE_API_USER_EMAIL_QUERY_FSRC`, and `DISCOURSE_API_CATEGORY_GROUPS_QUERY_{INTEREST}`, though that last one doesn't page since it's small enough not to need it). Also: `starts_at`/`ends_at` strings sometimes carry a UTC offset (`-05:00`); always call `.astimezone(ZoneInfo(tz_name))` after parsing so icalendar serialises `TZID=America/New_York` rather than `TZID="UTC-05:00"`.
- **A Data Explorer `int_list` param must be sent as a comma-separated string, not a native JSON array — sending an array silently drops the first element.** Root-caused live: a 63-event `DISCOURSE_API_EVENT_LOCATIONS_QUERY_{INTEREST}` run returned only 62 rows for 63 requested post ids. Isolated with single/paired-id test calls: `post_ids=[884]` alone → 0 rows; `post_ids=[973]` alone → 0 rows; `post_ids=[884, 973]` → only `973`; `post_ids=[973, 884]` (order swapped) → only `884`. The dropped element was always whichever id came first, regardless of which id it was (884 itself was fine — fetched cleanly via plain `/posts/884.json`, `deleted_at=None`) — consistent with Discourse stringifying the array server-side (e.g. Ruby's `[884, 973].to_s` → `"[884, 973]"`) before splitting on commas, so the leading `"["` corrupts only the first token's `to_i` parse to `0`, silently matching nothing for that element while the rest parse fine. Fixed by joining `post_ids` into a plain `"884,973"` string before passing it as the `post_ids` param in `fetch_event_locations()` (`community_calendar.py`) — confirmed live afterward: 144/144 posts returned for a full-range fetch, vs. 62/63 before the fix. This is the same class of gotcha as the boolean-param quirk above (`'true'` string vs Python `True`) — Discourse's params generally want plain strings, not native JSON types, even where JSON would parse into the "right" Ruby type. `fetch_event_locations()` also logs a `WARNING` naming any post id the query doesn't return a row for at all (distinct from a post that's returned but has no `location=` in its raw content), as a live tripwire if this class of param bug recurs.
- **`/admin/plugins/explorer/queries/{id}/run` (Data Explorer) is an admin-only endpoint** — it 401s (`fluent_discourse.errors.UnauthorizedError: Invalid credentials`) if run through a client authenticated as anything other than a Discourse admin account. This bit `community_calendar_views.calendar_feed()` specifically because it deliberately authenticates its main `discourse` client as `DISCOURSE_API_CALENDAR_USERNAME_{INTEREST}` (a low-privilege, "public"-equivalent account, on purpose — see Community Module Patterns above) to read events, but `fetch_event_locations()`'s Data Explorer query still needs an admin client. Fixed by building a second, separate `admin_discourse` client (default `INVITE_USERNAME`, same API key, via a plain `make_discourse_client(interest)` with no `username=` override) only when `location_query_id` is actually configured, and threading it through `filter_tags_to_bytes(..., admin_discourse=...)` for that one call — the low-privilege client is still used for everything else on that route.
- **`group_permissions` is not returned by any Discourse category API endpoint** on the FSRC instance (neither `/categories.json` nor `/categories/{id}.json`), even with an admin username. Category group permissions are fetched instead via a Discourse Data Explorer SQL query (`DISCOURSE_API_CATEGORY_GROUPS_QUERY_{INTEREST}`) that queries the `category_groups` table joined with `categories` and `groups`. The query must return columns `category_id`, `group_name`, `permission_type`. Falls back to displaying "Restricted" if the config key is absent.
- **A category's review-moderator group(s) are not on `GET /categories.json`.** There is no `reviewable_by_group_name`-style field despite that being the more commonly-referenced Discourse feature name for this. Use `GET /c/{id}/show.json` instead — `category.topic_posting_review_group_ids` and `category.reply_posting_review_group_ids` (both arrays of **group ids**, set independently for new-topic vs. reply review; a category can have more than one, e.g. FSRC's `public-calendar-events` has both `club-mods` and `cal-mods`). Resolve ids to names via `GET /groups.json` (`fetch_groups()` in `community_taxonomy.py`). Used by `community_review.fetch_category_moderator_groups()`.
- **`GET /review.json` pagination is unconfirmed and unsafe to page speculatively.** An initial implementation looped on `page=0,1,2,...` until an empty `reviewables` list came back; against the live instance it never terminated — Discourse kept returning the same non-empty page regardless of `page`, which burned through the 55-calls/60s rate limit repeatedly (visible as repeated `_RateLimiter.acquire(): throttling ~40s` log lines). Fixed by making a single request with a generously-sized `per_page` instead (`community_review.fetch_pending_reviewables()`), which is safe for a single category on a small club forum's review queue; it logs a warning (doesn't raise) if a response comes back at exactly `per_page`, since that would indicate real truncation. A reviewable's own record has no human-readable identity worth showing on its own — `id` is meaningless to a reader, and `created_at` is UTC/Zulu (e.g. `"2026-07-19T16:31:39.483Z"`). The response carries what's actually useful: `fancy_title` (falling back to `payload.title`; humanize the `type` field, e.g. `ReviewableQueuedPost` → "Queued Post", for reviewable types with no title, like a flagged post or new-user review) for what it is, and the sibling top-level `users` list resolved via each item's `target_created_by_id` for who submitted it — `community_review._reviewable_label()` builds `"<title> (submitted by <username>)"` from these. For display, convert `created_at` with `.astimezone()` (no explicit `ZoneInfo`) rather than the explicit-timezone pattern used elsewhere in this file's Discourse event handling — the container's `TZ` env var (`America/New_York`, set in `docker-compose.yml` for `app`/`crond`) makes bare `.astimezone()` resolve to local time correctly.

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
