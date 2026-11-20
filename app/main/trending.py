from app.models import Tag
from app.main import bp


@bp.app_context_processor
def inject_trending_tags():
    return {'trending_tags': Tag.trending}
