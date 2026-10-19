---
name: tag-parser
description: How hashtags are parsed in this project. Use when writing or testing code that extracts tags from post text.
---

<!-- Draft for the Kyriba workshop. Review before Friday. -->

# Hashtag parsing

- Match tags with the regex `#(\w+)`.
- Lower-case every tag.
- Store tags without the leading `#`.
- Return tags in order of first appearance, without duplicates.
- Text with no tags returns an empty list.
