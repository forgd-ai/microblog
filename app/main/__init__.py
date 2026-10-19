from flask import Blueprint

bp = Blueprint('main', __name__)


@bp.app_context_processor
def inject_trending():
    from app.trending import trending_box
    return {'trending_box': trending_box}


from app.main import routes
