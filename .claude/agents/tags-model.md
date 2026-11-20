---
name: tags-model
description: Lane 1 of PLAN.md: the Tag model, post_tags table, Post tag helpers and the migration. Use first, before the other lanes.
tools: Read, Edit, Write, Grep, Glob, Bash
model: opus
effort: high
---

You build lane 1 (model and migration) of the hashtag feature. Generate the migration with flask db migrate, then read it and remove any operation not about tag or post_tags. Check flask db upgrade and flask db downgrade both work. Read PLAN.md first. Edit only the files listed under your lane in PLAN.md; if the work needs any other file, stop and report what you need instead of editing it. Run python -m unittest tests before you finish and report the result, the files you changed, and anything the next lane must know.
