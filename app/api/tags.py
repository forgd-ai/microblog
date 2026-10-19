import sqlalchemy as sa
from flask import request, abort
from app import db
from app.models import Post, Tag
from app.api import bp
from app.api.auth import token_auth


@bp.route('/tags/<name>/posts', methods=['GET'])
@token_auth.login_required
def get_tag_posts(name):
    name = name.lower()
    tag = db.session.scalar(sa.select(Tag).where(Tag.name == name))
    if tag is None:
        abort(404)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    return Post.to_collection_dict(tag.posts_query(), page, per_page,
                                   'api.get_tag_posts', name=name)
