# Post rendering notes

Found by an Explore sweep. Not exhaustive: `app/api/tokens.py`, `errors.py`, `auth.py`, other templates and static files were not opened.

- `app/templates/_post.html:1` — the only partial that renders a post (avatar, author, timestamp, body, Translate link).
- `app/templates/_post.html:17` — body is output as `{{ post.body }}`.
- `app/templates/_post.html:18` — Translate link shown when `post.language` differs from `g.locale`.
- `app/templates/index.html:9` — includes `_post.html` (home feed and explore).
- `app/templates/user.html:40` — includes `_post.html` (profile page).
- `app/templates/search.html:5` — includes `_post.html` (search results).
- `app/templates/messages.html:5` — includes `_post.html` for Message objects, not Posts.
- `app/main/routes.py:28` — `index()` renders the home feed from `following_posts()`.
- `app/main/routes.py:56` — `explore()` renders all posts.
- `app/main/routes.py:73` — `user()` renders a user's posts.
- `app/main/routes.py:158` — `translate_text()` returns the translated body as JSON.
- `app/main/routes.py:167` — `search()` renders search results.
- `app/models.py:19` — `SearchableMixin.search` maps Elasticsearch hit IDs to Post rows.
- `app/models.py:166` — `User.following_posts()` is the home-feed query.
- `app/models.py:287` — `Post` model; has no `to_dict` and no API serializer.
- `app/search.py:4` — `add_to_index` serializes the post body into an Elasticsearch document.
- `app/tasks.py:36` — `export_posts` serializes each post to `{body, timestamp}`.
- `app/tasks.py:44` — `export_posts` emails the posts as a `posts.json` attachment.
- No RSS/feed output and no Jinja macro for posts were found.
