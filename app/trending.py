from datetime import datetime, timezone, timedelta
import sqlalchemy as sa
from flask import url_for
from werkzeug.routing import BuildError
from app import db
from app.models import Post, Tag, post_tags


def trending_tags(limit=5, days=7):
    """Return [(name, count)] for the most used tags in the last `days` days.

    Counts distinct posts per tag, ordered by count desc then name asc.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    count = sa.func.count(sa.distinct(Post.id)).label('count')
    query = (sa.select(Tag.name, count)
             .join(post_tags, post_tags.c.tag_id == Tag.id)
             .join(Post, Post.id == post_tags.c.post_id)
             .where(Post.timestamp >= since)
             .group_by(Tag.id, Tag.name)
             .order_by(count.desc(), Tag.name.asc())
             .limit(limit))
    return [(name, n) for name, n in db.session.execute(query)]


def trending_box():
    """Trending tags as dicts with a ready-made url, for the template."""
    items = []
    for name, n in trending_tags():
        try:
            url = url_for('main.tag', name=name)
        except BuildError:
            url = '/tag/' + name
        items.append({'name': name, 'count': n, 'url': url})
    return items
