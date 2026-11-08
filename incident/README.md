> **Workshop material.** This branch holds a planted bug for a training exercise. Never merge it into `main`.

# Incident: API clients stuck on 401

Reported on 3 November 2026 at 18:50 by the team that runs two internal services, feed-cache and report-export. Both use one shared API account.

- Since about 17:00, every API call from both services fails with 401.
- The services re-authenticate with `POST /api/tokens`. That returns 200 and a token, but the next call with that token still fails.
- The web UI works.
- A release went out at 16:45.

`access.log` in this folder is the app's access log from 13:00 to 19:00. 10.0.1.12 is feed-cache, 10.0.2.40 is report-export, and 10.0.9.x are browsers.

Find the cause, prove it with a failing test, and fix it.
