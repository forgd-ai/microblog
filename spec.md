# Spec: Hashtags

Source: `intent.md`. Tech lead decisions of 2026-11-07 are recorded under Decisions. Slice 1 is built now, slice 2 later.

## Data model
- A new `Tag` model has two columns: `id`, and `name` (`String(140)`, unique and indexed, stored lower-case without the `#`).
- A new `post_tag` association table works like `followers` (`app/models.py:88`):
  - `post_id` is a foreign key to `post.id` and `tag_id` is a foreign key to `tag.id`;
  - together they form the composite primary key;
  - it also gets an index on `tag_id`.
- `Post` gets a write-only `tags` relationship through `post_tag`, plus `PaginatedAPIMixin` and `to_dict()`. `Tag` gets a write-only `posts` relationship back.
- `parse_tags(body) -> list[str]` finds each `#` followed by ASCII letters, digits or underscores (the regex `#([A-Za-z0-9_]+)`). It returns the matches lower-cased, without duplicates, in the order they first appear.
- Saving a post: `index()` (`app/main/routes.py:29-38`) tags the post before its single commit. It reuses existing `Tag` rows and creates any that are missing.
- Migration: one new revision, made with `flask db migrate -m "tags"`. It creates the `tag` and `post_tag` tables, and its downgrade drops them. It changes no existing table.

## API contract: `GET /api/tags/<name>/posts`
- `@token_auth.login_required`; a missing or invalid token gets 401 `{"error": "Unauthorized"}`.
- `<name>` is lower-cased before the lookup. The tag is looked up with `db.first_or_404`, the same pattern `get_followers` uses with `get_or_404` (`app/api/users.py:28`). An unknown tag gets 404 `{"error": "Not Found"}`.
- `page` and `per_page` work as in `app/api/users.py:29-30`. The route returns `Post.to_collection_dict(query, page, per_page, 'api.get_tag_posts', name=<lowercased name>)`, where the query is the tag's posts, newest first.
- Each item has this shape:
  ```json
  {"id": 1, "body": "...", "timestamp": "2026-11-07T12:00:00+00:00",
   "language": "en" | null, "tags": ["python", "flask"],
   "_links": {"author": "/api/users/<user_id>"}}
  ```
  - `timestamp` is given the UTC timezone, as in `User.to_dict`.
  - A stored `language` of `''` is returned as `null`.
  - The item has no `self` link, because `GET /api/posts/<id>` doesn't exist yet.

## Out of scope
- A trending-tags box.
- Editing posts, and retagging a post after it is saved.
- Creating posts or editing tags through the API.
- Tag search or autocomplete.
- Following a tag.
- Fixing the missing validation of `page` and `per_page`. That is baseline issue 1, and the endpoint inherits it on purpose.

## Slices
**Slice 1 (now): the parser, saving tags, and the API endpoint**
- Files: `app/models.py`, `app/main/routes.py`, `app/api/tags.py` (new), `app/api/__init__.py`, `migrations/versions/<new>_tags.py`, `tests.py`.
- Tests:
  - `TagParseCase`: tests for `parse_tags` (see acceptance criteria 1-3).
  - `TagStorageCase`: posts the index form as a logged-in user and checks the stored rows. It uses a config with `WTF_CSRF_ENABLED = False`.
  - `TagAPICase`: tests for auth, 404, pagination, case-insensitive names, item shape and order.

**Slice 2 (later): links in posts and the `/tag/<name>` page**
- Files: `app/main/routes.py` (a new `tag` view, paged like `explore` at `app/main/routes.py:55-68`), `app/templates/_post.html:17` (the post body), a new Jinja filter `linkify_tags`, `app/translations/es/LC_MESSAGES/messages.po` (the new strings), `tests.py`.
- Tests: `TagPageCase` checks the links in a rendered post, HTML escaping, the `/tag/<name>` listing, its paging, and that the links keep the `/absproxy/<port>` prefix.

## Acceptance criteria
1. `parse_tags("#Flask and #flask, #py_3!")` returns `["flask", "py_3"]`.
2. `parse_tags("a#b, ##, #, email@x.com")` returns `["b"]`. A `#` inside a word counts.
3. `parse_tags("#café")` returns `["caf"]`, because tags are ASCII only.
4. Saving `"#A #a #b"` creates one `post_tag` row each for `a` and `b`. When a later post uses `#a`, it reuses the same `Tag` row.
5. Saving a post with tags commits only once, and works with `ELASTICSEARCH_URL=None`.
6. A request with no token gets 401 with the body `{"error": "Unauthorized"}`.
7. An unknown tag gets 404 with the body `{"error": "Not Found"}`.
8. `/api/tags/Python/posts` and `/api/tags/python/posts` return the same `items`.
9. With 3 tagged posts and `per_page=2`: there are 2 items, newest first; `_meta.total_items` is 3; `_links.next` is set; and `_links.self` contains `/api/tags/python/posts`.
10. `per_page=500` comes back as `_meta.per_page` = 100.
11. Each item matches the shape above, and a stored `language=''` is returned as `null`.
12. The migration upgrades and downgrades cleanly on SQLite.
13. (Slice 2) `#Flask` in a post renders as a link to `/tag/flask`. `<script>` in a post body is still escaped.

## Decisions (tech lead, 2026-11-07)
- **Schema change:** approved. Two new tables plus an index on `tag_id`. Existing tables don't change. The downgrade removes the tag data.
- **Tag length:** up to 139 characters, in a `String(140)` column. No shorter limit, and tags are never cut short.
- **Which characters count:** ASCII letters, digits and underscores only. `#café` is stored as `caf`, and `#2024` and `abc#def` are tags.
- **Unknown tag:** returns 404, not an empty 200, as the users API does for a missing parent resource.
- **Language and search:** `#` tags stay in the text used for language detection and the Elasticsearch index.
- **Editing posts:** out of scope. No edit route exists, so retagging is not needed.
- **Slice 2, translation:** no change needed. `translate()` reads the post with `innerText` (`app/templates/base.html:105`), so links don't change what is sent. A translated post shows plain text without links.

## Still open (no single default was proposed)
- **Old posts:** the proposal is a `flask tags backfill` command in `app/cli.py` that is safe to run more than once. It is not in slice 1. Decide when it ships: its own slice, or with slice 2.
- **Two posts creating the same new tag at once:** the unique index rejects one, and that request fails. Decide between retrying on `IntegrityError` and accepting the rare failure. Slice 1 accepts the failure until this is decided.
- **Deleting posts:** nothing in the app deletes posts today. If that is added, its `post_tag` rows must go too, by a foreign-key cascade or explicit cleanup.
