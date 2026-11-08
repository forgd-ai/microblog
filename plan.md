# Plan: Hashtags, slice 1 (parse, save, `GET /api/tags/<name>/posts`)

**Context:** Slice 1 of `spec.md`. Hashtags in a post are stored when it's saved, and API clients can list the posts with a tag. Tests come first. The code follows `.claude/skills/api-conventions`. This plan uses the name `parse_tags` instead of the spec's `extract_hashtags`; `spec.md` is updated to match.

## Decisions (accepted defaults, 2026-11-07)
- **Old posts:** not tagged in slice 1. A `flask tags backfill` command in `app/cli.py`, safe to run more than once, ships as its own small PR straight after slice 1. Until then, the endpoint only returns posts saved after release.
- **Two posts creating the same new tag at once:** accept the rare failed request. No retry on `IntegrityError`.
- **Deleting posts:** nothing deletes posts today, so slice 1 adds no cascade. Whatever change adds deletion must also remove the post's `post_tag` rows.

## 1. Tests first (`tests.py`); they fail until steps 2-4 are done
- `TagParseCase` (no app needed):
  - `parse_tags("I like #Python and #python_3")` returns `["python", "python_3"]`;
  - `parse_tags("#a #A #a")` returns `["a"]`;
  - `parse_tags("no tags here")` returns `[]`.
- `TagStorageCase`, with the same setUp/tearDown as `ProxyPrefixCase` (`tests.py:105-116`): a post with `"#x #X"`, tagged and committed, has one `post_tag` row, and a second post using `#x` reuses the same `Tag` row.
- `TagAPICase`, same setUp. It creates user `susan`, a token with `get_token()` (`app/models.py:259`) and `Post(body="#Python")`, tags it and commits.
  - `test_get_tag_posts`: `GET /api/tags/python/posts` with `Authorization: Bearer <token>` returns 200 with the post's id in `items`, and `_meta == {"page": 1, "per_page": 10, "total_pages": 1, "total_items": 1}`. These are the users API's keys and defaults (`app/models.py:70-75`, `app/api/users.py:19-20`).
  - `test_get_tag_posts_requires_token`: the same call with no header returns 401 `{"error": "Unauthorized"}`.

## 2. Model (`app/models.py`)
- `parse_tags(text)`, at module level: `re.findall(r'#([A-Za-z0-9_]+)', text)`, lower-cased, duplicates dropped in order (`dict.fromkeys`).
- A `post_tag` table, written like `followers` (`app/models.py:88-95`), with a composite primary key and an index on `tag_id`.
- A `Tag` model: `id`, and `name` (`String(140)`, unique and indexed), with a write-only `posts` relationship.
- `Post` gets `PaginatedAPIMixin`, a write-only `tags` relationship, and:
  - `add_tags_from_body()`: fetches existing tags in one `IN` query, creates the missing ones, and calls `self.tags.add_all(...)`. It doesn't commit.
  - `to_dict()`, in the shape from `spec.md` (`timestamp` in UTC as in `User.to_dict` at `app/models.py:231`, `language or None`, `tags`, `_links.author`).

## 3. Save hook (`app/main/routes.py:35-38`)
- Call `post.add_tags_from_body()` after `db.session.add(post)` and before the existing single `commit()`.

## 4. Endpoint: `app/api/tags.py` (new), plus an import in `app/api/__init__.py:5`
- `get_tag_posts(name)` has `@token_auth.login_required`, and looks the tag up with `db.first_or_404(sa.select(Tag).where(Tag.name == name.lower()))`.
- It reads `page` and `per_page` as `app/api/users.py:29-30` does, and returns `Post.to_collection_dict(tag.posts.select().order_by(Post.timestamp.desc()), page, per_page, 'api.get_tag_posts', name=tag.name)`.

## 5. Migration
- The local `app.db` is at head (`834b1a697901`). Run `flask db migrate -m "tags"`, then check that the file only creates `tag`, `post_tag` and their indexes, and that its downgrade drops them.
- On a copy of `app.db`, run `upgrade`, `downgrade -1` and `upgrade` again.

## 6. Verify
- `python -m unittest tests` passes, with 9 existing and 6 new tests. Then run the `test-runner` agent before committing.
- Manual check: post `#Python` in the web app, then `curl -H "Authorization: Bearer $T" localhost:5001/api/tags/PYTHON/posts`.

## Size check
- Estimated lines changed: `app/models.py` +50, `app/main/routes.py` +1, `app/api/tags.py` (new) +20, `app/api/__init__.py` +1/-1, the generated migration +40, `tests.py` +75, and `spec.md` (rename to `parse_tags`) about 4.
- Total: about 190 lines, of which about 150 are hand-written.
- All the code files are in slice 1's file list. `spec.md` is the only extra, and it's a documentation rename.
- This fits one reviewable pull request, so no split is needed. If it does need cutting down, the fallback is 1a (the model, migration, save hook and their tests) and 1b (the endpoint and its API tests).
