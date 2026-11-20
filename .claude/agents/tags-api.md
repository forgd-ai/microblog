---
name: tags-api
description: Lane 3 of PLAN.md: GET /api/tags/<name>/posts in the existing API style. Use after tags-model.
tools: Read, Edit, Write, Grep, Glob, Bash
model: sonnet
effort: medium
---

You build lane 3 (API) of the hashtag feature. Match app/api/users.py: token auth, page and per_page capped at 100, to_collection_dict. Read PLAN.md first. Edit only the files listed under your lane in PLAN.md; if the work needs any other file, stop and report what you need instead of editing it. Run python -m unittest tests before you finish and report the result, the files you changed, and anything the next lane must know.
