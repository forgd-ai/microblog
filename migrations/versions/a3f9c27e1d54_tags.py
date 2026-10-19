"""tags

Revision ID: a3f9c27e1d54
Revises: 834b1a697901
Create Date: 2026-10-19 12:00:00.000000

"""
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f9c27e1d54'
down_revision = '834b1a697901'
branch_labels = None
depends_on = None

# Frozen copy of app.tags.TAG_RE so this migration does not change behaviour
# if the app's parser changes later.
TAG_RE = re.compile(r'#(\w+)')


def upgrade():
    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=140), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tag', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tag_name'), ['name'],
                              unique=True)

    op.create_table(
        'post_tags',
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['post.id']),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id']),
        sa.PrimaryKeyConstraint('post_id', 'tag_id'),
    )
    with op.batch_alter_table('post_tags', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_post_tags_tag_id'), ['tag_id'],
                              unique=False)

    _backfill()


def _backfill():
    """Tag existing posts from their bodies."""
    conn = op.get_bind()
    post = sa.table('post', sa.column('id', sa.Integer),
                    sa.column('body', sa.String))
    tag = sa.table('tag', sa.column('id', sa.Integer),
                   sa.column('name', sa.String))
    post_tags = sa.table('post_tags', sa.column('post_id', sa.Integer),
                         sa.column('tag_id', sa.Integer))

    links = []
    names = set()
    for post_id, body in conn.execute(sa.select(post.c.id, post.c.body)):
        found = dict.fromkeys(m.lower() for m in TAG_RE.findall(body or ''))
        for name in found:
            links.append((post_id, name))
            names.add(name)
    if not links:
        return

    op.bulk_insert(tag, [{'name': name} for name in sorted(names)])
    tag_ids = dict((name, id) for id, name in conn.execute(
        sa.select(tag.c.id, tag.c.name)))
    op.bulk_insert(post_tags, [{'post_id': post_id, 'tag_id': tag_ids[name]}
                               for post_id, name in links])


def downgrade():
    with op.batch_alter_table('post_tags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_post_tags_tag_id'))
    op.drop_table('post_tags')

    with op.batch_alter_table('tag', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tag_name'))
    op.drop_table('tag')
