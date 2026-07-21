-- Discourse Data Explorer queries used by the community module.
--
-- These run inside Discourse itself (Admin -> Plugins -> Data Explorer), not
-- in this app's own database -- Discourse has no API to create or update a
-- Data Explorer query, only to run one by numeric id, so there is nothing in
-- this repo that can push these definitions into Discourse for you. This file
-- exists only as a git-tracked record of what each configured query id is
-- supposed to contain, since the admin panel is otherwise the only place
-- that knowledge lives. If you edit a query in the admin panel, update the
-- matching section here in the same change -- nothing enforces the two
-- staying in sync.
--
-- Each query's id goes into the matching DISCOURSE_API_*_QUERY_<INTEREST>
-- config key (see CLAUDE.md "Discourse Config Keys").


-- =============================================================================
-- DISCOURSE_API_EVENT_LOCATIONS_QUERY_<INTEREST>
-- Used by: community_calendar.fetch_event_locations()
-- Purpose: bulk-resolve [event location="..."] for a set of post ids, in one
--   (paged) call instead of one /posts/{id}.json REST call per calendar event.
-- Params: int_list :post_ids -- post ids to fetch raw content for. MUST be
--   passed as a comma-separated string (e.g. "884,973"), not a JSON array --
--   an array's first element is silently dropped server-side. See CLAUDE.md's
--   Discourse API Quirks note on this for how it was diagnosed.
-- Returns: id, raw -- location is parsed out of raw by fetch_event_locations()
-- =============================================================================

-- [params]
-- int_list :post_ids = 0
-- int :page_size = 1000
-- int :page_num = 0

SELECT id, raw
FROM posts
WHERE id IN (:post_ids)
ORDER BY id
LIMIT :page_size
OFFSET (:page_num * :page_size)


-- =============================================================================
-- DISCOURSE_API_CATEGORY_GROUPS_QUERY_<INTEREST>
-- Used by: community_taxonomy.fetch_category_groups()
-- Purpose: category group permissions -- not exposed by any Discourse category
--   REST endpoint on this instance (neither /categories.json nor
--   /categories/{id}.json), even with an admin username.
-- Params: (none currently passed by fetch_category_groups())
-- Returns: category_id, group_name, permission_type
-- =============================================================================

-- TODO: paste actual query text from Discourse Admin -> Plugins -> Data Explorer.
-- Known shape: joins category_groups with categories and groups.


-- =============================================================================
-- DISCOURSE_API_INVITES_QUERY_FSRC
-- Used by: CommunitySyncManager.start_import() (community.py)
-- Purpose: pending Discourse invites, to reconcile against community group
--   membership for people who haven't signed up yet.
-- Params: :page_size / :page_num (paged via community.run_query_paged())
-- Returns: id, email, deleted_at, invalidated_at, redemption_count
--   (only rows with email set, not deleted/invalidated, and
--   redemption_count == 0 are kept -- see start_import())
-- =============================================================================

-- TODO: paste actual query text from Discourse Admin -> Plugins -> Data Explorer.


-- =============================================================================
-- DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC
-- Used by: CommunitySyncManager.start_import() (community.py)
-- Purpose: which groups each pending invite (see INVITES_QUERY above) is
--   targeted at.
-- Params: :page_size / :page_num (paged via community.run_query_paged())
-- Returns: invite_id, group_id
-- =============================================================================

-- TODO: paste actual query text from Discourse Admin -> Plugins -> Data Explorer.


-- =============================================================================
-- DISCOURSE_API_USER_EMAIL_QUERY_FSRC
-- Used by: CommunitySyncManager (community.py)
-- Purpose: map email addresses to Discourse user ids, since Discourse's own
--   user-listing REST endpoints don't return email addresses.
-- Params: :page_size / :page_num (paged via community.run_query_paged())
-- Returns: email, user_id
-- =============================================================================

-- TODO: paste actual query text from Discourse Admin -> Plugins -> Data Explorer.
