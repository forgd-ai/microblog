# Intent: Hashtags

## Problem
Posts can't be grouped by topic. A `#word` in a post is plain text: it isn't stored or linked, and there's no way to find other posts that use it, either in the web app or through the API.

## Outcome
- **Now (slice 1):** when a post is saved, every hashtag in its body is stored. A hashtag is `#` followed by ASCII letters, digits or underscores; it's stored lower-case, without the `#`, once per post.
- **Now (slice 1):** `GET /api/tags/<name>/posts` returns the posts that have that tag, as JSON. Names match case-insensitively, so `/api/tags/Python/posts` and `/api/tags/python/posts` give the same result. Posts come back newest first, and an unknown tag gets 404.
- **Later (slice 2):** in the web app, each `#tag` in a post links to `/tag/<name>`, and that page lists the tagged posts.
- **Out of scope:** a trending-tags box, and editing posts (so no retagging).

## Affected users and systems
- **Users:** people who post hashtags, and API clients that read posts by tag. In the later phase, also web readers.
- **Saving posts:** `index()` in `app/main/routes.py:29-38` is the only place posts are created, so it's the only place tags are extracted.
- **Data model:** `Post` (`app/models.py:287`) gains a tag relationship, plus `to_dict()` and `PaginatedAPIMixin`, none of which it has today. Adding a tag table and a link table requires a new Alembic migration in `migrations/versions/`.
- **API:** a new module under `app/api/`, imported in `app/api/__init__.py:5`.
- **Tests:** a new test class in `tests.py` for the endpoint. No test touches `/api/` today.

## Constraints
- The endpoint follows the users-API conventions (`.claude/skills/api-conventions/SKILL.md`):
  - it requires `@token_auth.login_required`;
  - it reads `page`/`per_page` from the query string and caps `per_page` at 100;
  - it returns `to_collection_dict(..., 'api.<endpoint>', name=...)`;
  - errors go through `app/api/errors.py`.
- Because the endpoint copies that pagination, it also inherits the existing missing validation of `page` and `per_page` (baseline issue 1). That should be fixed separately, not blamed on this feature.
- `post.timestamp` has no timezone in the database, so `Post.to_dict()` must add UTC itself, as `User.to_dict()` does. A failed language detection stores `language=''`, which the API returns as `null`.
- Each commit runs the Elasticsearch hooks (`app/models.py:33-60`). Tagging must not add a second commit or break when Elasticsearch is off, as it is in tests.
- Migrations must work on SQLite, in batch mode like the existing ones.
- The body is limited to 140 characters (`app/models.py:290`), so a tag can be at most 139 characters long. There is no shorter limit.

## Open questions
Decided by the tech lead on 2026-11-07 (details in `spec.md`):
- An unknown tag returns 404. A tag repeated in one post is stored once. Posts come back newest first.
- Tags are ASCII only, up to 139 characters.
- `#` tags stay in the text used for language detection and the search index.
- Editing posts is out of scope. Slice 2 (the web phase) comes later and is paged like `explore`.

Still open:
1. **Old posts:** they will be tagged by a `flask tags backfill` command that is safe to run more than once, but it isn't in slice 1. When does it ship? Until it does, the endpoint only returns posts saved after release.
2. **Two posts creating the same new tag at once:** retry on `IntegrityError`, or accept the rare failed request? Slice 1 accepts the failure for now.
3. **Deleting posts:** nothing deletes posts today. If that is added, its tag links must be removed too.
