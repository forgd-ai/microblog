"""Hashtag parsing, following .claude/skills/tag-parser."""
import re

TAG_RE = re.compile(r'#(\w+)')


def extract_tags(body):
    """Return the tags in ``body``: lower-cased, without the ``#``, and
    de-duplicated in order of first appearance."""
    if not body:
        return []
    return list(dict.fromkeys(m.lower() for m in TAG_RE.findall(body)))
