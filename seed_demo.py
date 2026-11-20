"""Recreate the demo user and a few tagged posts after a database reset.

Run from the repo root with the venv active:
    rm -f app.db && flask db upgrade && python seed_demo.py
Sign in as demo / demo. Running it twice changes nothing.
"""
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from app import create_app, db
from app.models import User, Post

POSTS = [
    ('Trying the new #hashtags feature on #flask', timedelta(hours=1)),
    ('#python and #flask make a small app quick to build',
     timedelta(hours=5)),
    ('Six sub-agents built this one #claudecode', timedelta(days=1)),
    ('More #python on a quiet afternoon', timedelta(days=3)),
    ('An older post about #flask, outside the trending window',
     timedelta(days=10)),
]


def seed():
    user = db.session.scalar(sa.select(User).where(User.username == 'demo'))
    if user is not None:
        print('demo user already exists')
        return
    user = User(username='demo', email='demo@example.com')
    user.set_password('demo')
    db.session.add(user)
    now = datetime.now(timezone.utc)
    for body, age in POSTS:
        post = Post(body=body, author=user, language='en',
                    timestamp=now - age)
        db.session.add(post)
        post.set_tags_from_body()
    db.session.commit()
    print('created demo user (password: demo) and {} posts'.format(
        len(POSTS)))


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
