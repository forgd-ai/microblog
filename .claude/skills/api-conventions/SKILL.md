---
name: api-conventions
description: How we build a JSON endpoint in this repo. Use when adding or changing a route in app/api/ or its tests.
---

# API conventions

**Routes**
- Put routes on the `api` blueprint (`bp`, `app/api/__init__.py:3`) in a module under `app/api/`, and add that module to the import line at `app/api/__init__.py:5`. The blueprint is mounted at `/api` (`app/__init__.py:84`).
- Every route has `@token_auth.login_required` (`app/api/users.py:11`). There are two exceptions: user sign-up, `POST /api/users`, has no auth (`app/api/users.py:45-46`), and `POST /api/tokens` uses `@basic_auth.login_required` (`app/api/tokens.py:7`).

**Responses**
- Collections: read `page` and `per_page` from `request.args`, cap `per_page` with `min(..., 100)`, and return `Model.to_collection_dict(query, page, per_page, 'api.<endpoint>')`. Pass any URL args as kwargs (`app/api/users.py:19-22`, `app/api/users.py:29-32`).
- Single item: `return db.get_or_404(Model, id).to_dict()` (`app/api/users.py:13`).

**Errors**
- Return `bad_request(message)` for a 400 (`app/api/errors.py:13`, used at `app/api/users.py:49`), or `error_response(status, message)` for any other status (`app/api/errors.py:6`).
- An uncaught `HTTPException` (for example from `abort(403)`) is turned into a JSON response by `app/api/errors.py:17-19`.

**Tests**
- Tests are `unittest.TestCase` classes in `tests.py`. In `setUp`, call `create_app(TestConfig)`, push an app context, run `db.create_all()`, and use `self.app.test_client()`. `tearDown` undoes these steps. See `ProxyPrefixCase` (`tests.py:105-116`). `TestConfig` (`tests.py:9`) uses in-memory SQLite.
