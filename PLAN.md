# PLAN: hashtags

## Goal

- `#tags` in a post body are stored and shown as links.
- `/tag/<name>` lists posts with that tag, paginated like the index.
- `GET /api/tags/<name>/posts` returns them as JSON in the existing API style.
- The index page shows the 5 most used tags this week.

## Facts from exploration

- `Post` is in `app/models.py`: `body` is `String(140)`, `timestamp` is indexed, and `user_id` and `language` are columns. It has no `to_dict` and no API mixin.
- Posts are created only in `index()` in `app/main/routes.py`. That function also detects the language and commits.
- Migrations use Flask-Migrate (Alembic, `migrations/versions/`). The current head is `834b1a697901` (user tokens).
- Pagination follows the index pattern: `db.paginate(query, page, per_page=POSTS_PER_PAGE)` plus `next_url` and `prev_url`, rendered by `index.html`.
- Post rows render in `app/templates/_post.html`. The body sits in `<span id="post{{ post.id }}">`, which the translate link reads.
- API routes live in the `api` blueprint (`app/api/`). Each requires `@token_auth.login_required`, returns a dict, and uses `PaginatedAPIMixin.to_collection_dict` for lists. Errors go through `app/api/errors.py`.
- `tests.py` uses `unittest` with an in-memory SQLite `TestConfig`. Run it with `python -m unittest tests`.

## Tag rules

- A tag is `#` followed by 1-50 letters, digits or underscores.
- It must not follow a letter, digit, `_` or `&`, so `a#b` and `&#39;` are not tags.
- Tags are stored lowercase and deduplicated per post.

## Lanes

Every file belongs to exactly one lane. An agent edits only the files its lane lists.

### Lane 1 - model and migration

- **Files:** `app/models.py`, `migrations/versions/*_post_tags.py`
- **Depends on:** nothing
- **Work:**
  - Add a `Tag` model (`id`, `name` unique and indexed) and a `post_tags` association table.
  - Add a `Post.tags` many-to-many relationship.
  - Add `Post.set_tags_from_body()`, a `TAG_PATTERN` regex and `Tag.trending(limit=5, days=7)`.
  - Add `Post.to_dict()` and `PaginatedAPIMixin` on `Post`.
  - Add a migration from head `834b1a697901` that covers only `tag` and `post_tags`.
- **Done when:**
  - `flask db upgrade` applies cleanly.
  - `flask db downgrade` removes both tables.
  - The existing tests still pass.

### Lane 2 - web routes and templates

- **Files:** `app/main/routes.py`, `app/templates/_post.html`, `app/templates/tag.html`
- **Depends on:** lane 1
- **Work:**
  - Call `post.set_tags_from_body()` when a post is created.
  - Add the `/tag/<name>` route, paginated like `explore`, returning 404 for an unknown tag.
  - Add a `linkify_tags` template filter that escapes the body and links each tag.
  - Render the post body through that filter.
- **Done when:**
  - A new post with `#flask` shows `#flask` as a link.
  - `/tag/flask` lists it.
  - Pagination links work.

### Lane 3 - API

- **Files:** `app/api/tags.py`, `app/api/__init__.py`
- **Depends on:** lane 1
- **Work:**
  - Add `GET /api/tags/<name>/posts`, token-protected, with `page` and `per_page` (capped at 100).
  - Return the result through `Post.to_collection_dict`, newest first.
  - Return 404 for an unknown tag.
- **Done when:** the endpoint returns `items`, `_meta` and `_links` like `/api/users`.

### Lane 4 - trending box

- **Files:** `app/main/trending.py`, `app/main/__init__.py`, `app/templates/_trending.html`, `app/templates/index.html`
- **Depends on:** lane 1
- **Work:**
  - Add a context processor that exposes `trending_tags()`.
  - Add a `_trending.html` partial listing up to 5 tags with counts and links to `/tag/<name>`.
  - Include the partial on the home page only.
- **Done when:**
  - The home page shows this week's top 5 tags, most used first.
  - Tags from posts older than 7 days are not counted.

### Lane 5 - tests

- **Files:** `tests.py`
- **Depends on:** lanes 1-4
- **Work:**
  - Test tag parsing: case, duplicates, `a#b` and entities.
  - Test `Tag.trending`: order, the limit, and the 7-day window.
  - Test the `/tag/<name>` page: listing and the 404.
  - Test the API endpoint: shape, the 404 and the 401 without a token.
  - Test link rendering.
- **Done when:** `python -m unittest tests` passes.

## Outside the lanes

- `seed_demo.py` is a checkpoint helper, not part of the feature. After a database reset it recreates the `demo` user (password `demo`) and five tagged posts.

## Order

Lane 1 runs first. Lanes 2, 3 and 4 then run in parallel, followed by lane 5 and finally a read-only review of the diff against this plan.

## Status

- [x] Lane 1 - model and migration: `Tag`, `post_tags`, `Post.tags`, `Post.set_tags_from_body()`, `Tag.trending()`, `Post.to_dict()`; migration `765dc8e29d56` (tag and post_tags only; upgrade and downgrade checked)
- [x] Lane 2 - web routes and templates: tags stored on post create, `/tag/<name>` paginated with 404 for unknown tags, `linkify_tags` filter escapes the body
- [x] Lane 3 - API: `GET /api/tags/<name>/posts`, token auth, `per_page` capped at 100, 404 for unknown tags
- [x] Lane 4 - trending box: `trending_tags()` context processor, `_trending.html` on the home page only
- [x] Lane 5 - tests: 10 new tests in `HashtagCase`; `python -m unittest tests` runs 19 tests, all pass
- [x] Review: every changed file belongs to one lane; no findings above low
