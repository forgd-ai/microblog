# Hashtag feature plan

Goal:
- `#tags` in a post body are stored and shown as links.
- `/tag/<name>` lists posts with that tag, paginated like the index.
- `GET /api/tags/<name>/posts` returns them as JSON in the existing API style.
- The index page shows the 5 most used tags this week.

## Shared contract (original plan, superseded: see Status and the code for the current version)

Every lane builds against this. Change it here first, then tell the other lanes.

- **Parsing** follows `.claude/skills/tag-parser`: regex `#(\w+)`, lower-case, stored without the `#`, de-duplicated per post.
  - `app/tags.py` exposes `extract_tags(body) -> list[str]` and `TAG_RE`.
- **Schema:**
  - `Tag(id, name)` has a unique, indexed, lower-case `name`.
  - `post_tags(post_id, tag_id)` is the association table, with a composite primary key and both columns as foreign keys.
  - `Post.tags` and `Tag.posts` are the two sides of the relationship.
- **Writing tags:** `Post.set_tags(names)` replaces the post's tags, creating missing `Tag` rows. The index view calls `post.set_tags(extract_tags(body))` before commit.
- **Reading a tag's posts:** `Tag.posts_query()` returns a `sa.select(Post)` ordered by `Post.timestamp` desc. The web and API lanes both use it.
- **Serializing:** `Post` gets `PaginatedAPIMixin` and `Post.to_dict()` returning `id, body, timestamp (ISO, UTC), language, tags, author` and `_links{self?, author, tag pages}`. This is needed because `Post` has no `to_dict` today (`app/models.py:287`).
- **Trending:** `trending_tags(limit=5, days=7) -> list[(name, count)]`. It counts distinct posts per tag over a rolling window of `now - 7 days`, ordered by count desc then name asc.

## Status

- **Lane 1 (tags-model): done, with two checks outstanding.**
  - Built: `app/tags.py`, the `Tag`/`post_tags`/`Post.tags`/`set_tags`/`posts_query`/`to_dict` changes in `app/models.py`, and `migrations/versions/a3f9c27e1d54_tags.py` (down_revision `834b1a697901`, with backfill).
  - Verified: `extract_tags` output, `set_tags` replace and reuse, and `python -m unittest tests` (9 tests, OK).
  - **Not run:** `flask db upgrade` / `downgrade -- -1` on a populated DB, and `flask db heads`. The agent could not run `flask` in its sandbox.
  - Contract changes the other lanes must follow:
    - `posts_query()` is an instance method: look the tag up by name, then call `tag.posts_query()`. It is not `Tag.posts_query(...)`.
    - `Post.to_dict()`: `author` is the user id, `_links.tags` is a `{name: url}` dict, and `_links.self` is omitted. Tag URLs come from `url_for('main.tag', name=...)`, so lane 2 must name its view `tag`. Until it exists the URL is `None`.
    - `post_tags.tag_id` has an extra index.
- **Lane 3 (tags-api): written, not verified.**
  - Built: `app/api/tags.py` (`get_tag_posts`, `GET /api/tags/<name>/posts`, token auth, lower-cased name, JSON 404 for an unknown tag, `page`/`per_page` capped at 100, `tag.posts_query()`), and `tags` added to the import in `app/api/__init__.py`.
  - **Not run:** every "Done when" check (200 shape, pagination links, 404, 401) and the unit tests. The agent's Bash call was denied.
- **Lane 2 (tags-web): written, not verified.**
  - Built in `app/main/routes.py`: `index()` calls `post.set_tags(extract_tags(...))`; the `linkify_tags` filter is registered with `@bp.app_template_filter`, so `app/__init__.py` is untouched; the `/tag/<name>` view is named `tag` and uses `tag.posts_query()`.
  - Built in templates: `_post.html` uses `post.body|linkify_tags`, and `tag.html` is new.
  - Deviation: `/tag/<name>` has `@login_required`, like the other main views.
  - The Translate link was checked by reading the code only: the JS writes to `#translation<id>`, not `#post<id>`.
  - **Not run:** every "Done when" check and the unit tests. The agent's Bash call was denied.
- **Lane 4 (tags-trending): written, not verified.**
  - Built: `app/trending.py` (`trending_tags(limit=5, days=7)`, one grouped query with `count(distinct Post.id)`), `app/templates/_trending.html`, an `app_context_processor` in `app/main/__init__.py`, and one `{% include %}` in `index.html`.
  - Deviation: the context processor exposes `trending_box` (from a new `trending_box()` helper in `app/trending.py` that adds URLs), not `trending_tags`. The `trending_tags()` contract is unchanged.
  - The box also shows on Explore; it is not gated on `form`.
  - **Risk:** `Post.timestamp` is naive UTC on SQLite and is compared with a timezone-aware `datetime`. Lane 5's window-boundary test must cover this.
  - **Not run:** every "Done when" check and the unit tests. The agent's Bash call was denied.
- **Lane 5 (tags-tests): done, with gaps.**
  - Built: 37 new tests in `tests.py` (parser, model, trending, web, API), plus a `DbCase` base class, a `get_token` helper and `WTF_CSRF_ENABLED = False` in `TestConfig`.
  - Verified: `venv/bin/python -m unittest tests` ran 46 tests (9 existing, 37 new), all passing. This is the first real run of lanes 2-4, so it also covers their code paths. The trending window boundary is correct on SQLite; other databases were not tested.
  - Finding in lane 1: `Post.set_tags` (`app/models.py:321`) runs a `SELECT` before the post is in the session, which raises a SQLAlchemy `SAWarning` via autoflush. It is harmless today. A fix is `db.session.no_autoflush` around the lookup, or adding the post first.
  - **Not done:** checking that each test fails without its lane's change, the Translate link check (needs a browser), and the migration checks (`flask db upgrade`, `downgrade -- -1`, `heads`).
- **Review (tags-reviewer): done. Open issues, not fixed.**
  - **High:** `linkify_tags` (`app/main/routes.py`) escapes first, then matches. `'` becomes `&#39;` and `"` becomes `&#34;`, so `#39` and `#34` match as tags and link to `/tag/39`, which is a 404. This is a display bug, not XSS. Fix: match on the raw body and escape the pieces between matches. No test covers it.
  - **Medium:**
    - The migration has never been run (`upgrade`, `downgrade -- -1`, `heads`, `db check`). The reviewer could not run `flask` either.
    - The SAWarning in `Post.set_tags` (`app/models.py:321`) fires on every new post in production, because `index()` calls `set_tags` before `db.session.add(post)`. Fix: `db.session.no_autoflush` around the lookup.
    - `test_tag_page_lists_only_tagged_posts` always passes, because the heading "Posts tagged #flask" contains `tagged`. It should assert the post text.
    - "Each test fails without its lane's change" was never checked, and the Translate link has not been tested in a browser.
  - **Low:**
    - The contract and lane text above still describe the old versions of `posts_query`, `to_dict` and the context-processor name. Only this Status section is current.
    - Two posts creating the same new tag at once can raise an `IntegrityError` (500).
    - The trending cutoff is timezone-aware against a naive column, which is only tested on SQLite.
    - `_trending.html` calls `trending_box()` from the template and runs a query on every Index and Explore load.
    - Two `BuildError` fallbacks are dead code. The one in `trending_box` would also skip the `/absproxy` prefix.
    - The API runs one extra tag query per post.
  - The reviewer found every lane inside its file list.

## Lanes

Lanes 1 and 5 depend on nothing. Lanes 2, 3 and 4 only need the contract, so they can start in parallel against stubs. Each lane's file list is exclusive: no file appears in two lanes.

### Lane 1: model + migration

Files it may touch:
- `app/models.py` (`Tag`, `post_tags`, `Post.tags`, `Post.set_tags`, `Tag.posts_query`, `Post` + `PaginatedAPIMixin`, `Post.to_dict`)
- `app/tags.py` (new)
- `migrations/versions/<rev>_tags.py` (new)

Depends on: nothing.

Migration details:
- It creates `tag` and `post_tags`.
- Its `down_revision` is `834b1a697901`, the current head.
- It backfills tags from existing post bodies (see open question 3).

Done when:
- `flask db upgrade` and `flask db downgrade -- -1` both run cleanly on a copy of a populated DB.
- `flask db heads` shows a single head.
- `python -c "from app.tags import extract_tags; print(extract_tags('Hi #Flask #flask #a_b'))"` prints `['flask', 'a_b']`.
- `set_tags` replaces tags instead of accumulating them, and reuses existing `Tag` rows.

### Lane 2: web routes + templates

Files it may touch:
- `app/main/routes.py` (the post-creation call in `index()` at line 35 and a new `/tag/<name>` view)
- `app/__init__.py` (register the Jinja filter, if it can't live in the blueprint)
- `app/templates/_post.html` (line 17, the body output)
- `app/templates/tag.html` (new)

It must not touch `index.html`; that is lane 4's file.

Depends on: lane 1's contract. It can start with a stub `extract_tags` and `Tag`.

Behaviour:
- `index()` calls `post.set_tags(extract_tags(...))` before commit.
- `/tag/<name>` lower-cases `name`, returns 404 for an unknown tag, and uses `db.paginate` with `POSTS_PER_PAGE` and `error_out=False`. It builds `next_url` and `prev_url` as `index` does (`routes.py:41-47`).
- A Jinja filter `linkify_tags` escapes the body first, then wraps each `#tag` match in `<a href="/tag/<name>">`, and returns `Markup`.
  - Escaping first keeps `{{ post.body }}` XSS-safe.
  - `_post.html` calls the filter instead of printing `post.body`. The `.claude/rules/templates.md` rule says no logic in templates, so the regex stays in Python.
- `tag.html` extends `base.html` and copies the existing Bootstrap pager from `index.html`. It includes `_post.html` for each post.
- The `_post.html` change also applies to profile and search pages, which include the same partial.

Done when:
- Posting `Hello #Flask` as a logged-in user shows `#Flask` as a link to `/tag/flask`.
- `/tag/flask` lists that post.
- With `POSTS_PER_PAGE` + 1 tagged posts, page 2 appears and the Newer/Older links work.
- `/tag/nosuchtag` returns 404.
- A post body of `<script>alert(1)</script> #x` renders escaped, with only `#x` as a link.
- The Translate link still works on a tagged post. The JS replaces the text of `#post<id>`, so check that it doesn't break the links.

### Lane 3: API

Files it may touch:
- `app/api/tags.py` (new)
- `app/api/__init__.py` (add `tags` to the import on line 5)

Depends on: lane 1 (`Tag`, `Post.to_dict`, `PaginatedAPIMixin`).

Behaviour:
- `GET /api/tags/<name>/posts` uses `@token_auth.login_required`, like every other API `GET`.
- It lower-cases `name`, and an unknown tag returns the JSON 404 from `error_response` through `abort(404)`.
- It reads `page` (default 1) and `per_page` (default 10, capped at 100), then returns `Post.to_collection_dict(Tag.posts_query(...), page, per_page, 'api.get_tag_posts', name=name)`.
- The response shape is `{items, _meta, _links}`, as in `GET /api/users`.

Done when, with a token from `POST /api/tokens`:
- the endpoint returns 200 with the `{items, _meta, _links}` shape;
- `per_page=2` paginates and the `_links.next` and `prev` URLs work;
- an unknown tag returns a JSON 404;
- a request without a token returns the JSON 401.

### Lane 4: trending box

Files it may touch:
- `app/trending.py` (new, `trending_tags()`)
- `app/templates/_trending.html` (new)
- `app/templates/index.html` (one `{% include %}`, and nothing else)
- `app/main/__init__.py` or `app/__init__.py` (a context processor exposing `trending_tags`, if no better place)

Depends on: lane 1's `Tag` and `post_tags`.

Behaviour:
- It runs one grouped query joining `post_tags`, `Tag` and `Post`, filtering on `Post.timestamp >= now - 7 days`, with `count(distinct Post.id)`, ordered by count desc then name asc, limit 5.
- The box shows each tag as a link to `/tag/<name>` with its count, and hides itself or says so when there are none.
- Explore also renders `index.html`, so it gets the box too. If that's unwanted, gate it on `form`.

Done when:
- With seeded posts at known ages and tags, the box shows exactly the top 5, ordered correctly, with correct counts.
- A post older than 7 days doesn't count.
- A tag used twice in one post counts once.
- A tie is broken by name.
- A DB with no tags shows no errors.

### Lane 5: tests

Files it may touch:
- `tests.py` only.

Depends on: the contract, and the other lanes for the tests to pass. It can write them first against the contract, and they are expected to fail until lanes 1-4 land.

Add to `tests.py`, using the existing `setUp` and `tearDown` (in-memory SQLite, `ELASTICSEARCH_URL=None`) and the `ProxyPrefixCase` test-client setup:
- **Parser:** lower-casing, de-duplication, `#` alone, `#123`, punctuation after a tag, no tags.
- **Model:** `set_tags` replaces, `Tag.posts_query` ordering, and `Post.to_dict`.
- **Trending:** window boundary, distinct-post counting, tie-break, and the limit of 5.
- **Web:** posting creates tags, `/tag/<name>` pagination and 404, escaping, and the link rendering.
- **API:** token flow, the collection shape, pagination, 404 and 401. These are the first API tests in the repo, so include a small helper that fetches a token.

Done when `python -m unittest tests` passes with every lane merged, and each test fails without its lane's change.

## Merge order

1. Lane 1, then rebase the others on it.
2. Lanes 2, 3 and 4, in any order.
3. Lane 5 last, or merged progressively as each lane lands.

## Open questions

1. **What counts as a tag?** `#(\w+)` also matches `#123` and the fragment in `http://x/#anchor`. The skill says to use `\w+`; do we keep that, or require a leading space or start of string and at least one letter?
2. **Window:** "this week" means a rolling 7 days in this plan, not calendar Monday to Sunday.
3. **Backfill:** this plan backfills existing posts in the migration so tag pages and trending aren't empty after deploy. The alternative is to tag new posts only.
4. **Editing or deleting posts:** the app has neither today, so there's no tag cleanup. Orphan `Tag` rows are harmless.
5. **Search and export:** the Elasticsearch index and `export_posts` (`app/tasks.py:36`) stay as they are. Neither includes tags.

## Fix round 1

- `linkify_tags` now links tags found in the raw body and escapes each piece, so `it's #python` links only `/tag/python`.
- `Post.set_tags` runs its lookup under `no_autoflush` (no SAWarning).
- `test_tag_page_lists_only_tagged_posts` now asserts the tagged post body renders and the untagged one is absent.
- Migration verified by hand: `flask db upgrade`, `downgrade -- -1`, `upgrade` and a single head all work on a scratch DB.
