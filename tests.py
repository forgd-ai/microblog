#!/usr/bin/env python
from datetime import datetime, timezone, timedelta
import unittest
from app import create_app, db
from app.models import User, Post, Tag
from app.tags import extract_tags
from app.trending import trending_tags
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False


class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan', email='susan@example.com')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_avatar(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))

    def test_follow(self):
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        following = db.session.scalars(u1.following.select()).all()
        followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(following, [])
        self.assertEqual(followers, [])

        u1.follow(u2)
        db.session.commit()
        self.assertTrue(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 1)
        self.assertEqual(u2.followers_count(), 1)
        u1_following = db.session.scalars(u1.following.select()).all()
        u2_followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(u1_following[0].username, 'susan')
        self.assertEqual(u2_followers[0].username, 'john')

        u1.unfollow(u2)
        db.session.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 0)
        self.assertEqual(u2.followers_count(), 0)

    def test_follow_posts(self):
        # create four users
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        u3 = User(username='mary', email='mary@example.com')
        u4 = User(username='david', email='david@example.com')
        db.session.add_all([u1, u2, u3, u4])

        # create four posts
        now = datetime.now(timezone.utc)
        p1 = Post(body="post from john", author=u1,
                  timestamp=now + timedelta(seconds=1))
        p2 = Post(body="post from susan", author=u2,
                  timestamp=now + timedelta(seconds=4))
        p3 = Post(body="post from mary", author=u3,
                  timestamp=now + timedelta(seconds=3))
        p4 = Post(body="post from david", author=u4,
                  timestamp=now + timedelta(seconds=2))
        db.session.add_all([p1, p2, p3, p4])
        db.session.commit()

        # setup the followers
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u3)  # susan follows mary
        u3.follow(u4)  # mary follows david
        db.session.commit()

        # check the following posts of each user
        f1 = db.session.scalars(u1.following_posts()).all()
        f2 = db.session.scalars(u2.following_posts()).all()
        f3 = db.session.scalars(u3.following_posts()).all()
        f4 = db.session.scalars(u4.following_posts()).all()
        self.assertEqual(f1, [p2, p4, p1])
        self.assertEqual(f2, [p2, p3])
        self.assertEqual(f3, [p3, p4])
        self.assertEqual(f4, [p4])


class ProxyPrefixCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_absproxy_request_builds_prefixed_links(self):
        rv = self.client.get('/absproxy/5001/auth/register')
        self.assertEqual(rv.status_code, 200)
        html = rv.get_data(as_text=True)
        self.assertIn('href="/absproxy/5001/auth/login"', html)
        self.assertIn("fetch('/absproxy/5001/translate'", html)
        self.assertIn("fetch('/absproxy/5001/user/'", html)

    def test_absproxy_redirect_keeps_prefix(self):
        rv = self.client.get('/absproxy/5001/')
        self.assertEqual(rv.status_code, 302)
        self.assertTrue(rv.headers['Location'].startswith(
            '/absproxy/5001/auth/login'), rv.headers['Location'])

    def test_plain_request_builds_links_without_prefix(self):
        rv = self.client.get('/auth/register')
        self.assertEqual(rv.status_code, 200)
        html = rv.get_data(as_text=True)
        self.assertIn('href="/auth/login"', html)
        self.assertIn("fetch('/translate'", html)
        self.assertIn("fetch('/user/'", html)
        self.assertNotIn('absproxy', html)

    def test_malformed_prefix_is_not_rewritten(self):
        rv = self.client.get('/absproxy/5001auth/login')
        self.assertEqual(rv.status_code, 404)
        self.assertNotIn('absproxy/5001/', rv.get_data(as_text=True))

    def test_prefix_alone_serves_the_root(self):
        rv = self.client.get('/absproxy/5001')
        self.assertEqual(rv.status_code, 302)
        self.assertTrue(rv.headers['Location'].startswith(
            '/absproxy/5001/auth/login'), rv.headers['Location'])


class DbCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def make_user(self, username='john', password='cat'):
        u = User(username=username, email=f'{username}@example.com')
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    def make_post(self, author, body, age=timedelta(0), tags=None):
        """Create a post `age` old. Tags default to those parsed from body."""
        p = Post(body=body, author=author,
                 timestamp=datetime.now(timezone.utc) - age)
        p.set_tags(extract_tags(body) if tags is None else tags)
        db.session.add(p)
        db.session.commit()
        return p

    def login(self, username='john', password='cat'):
        rv = self.client.post('/auth/login', data={
            'username': username, 'password': password})
        self.assertEqual(rv.status_code, 302)


class TagParserCase(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(extract_tags('Hi #Flask'), ['flask'])

    def test_deduplicates_case_insensitively_in_order(self):
        self.assertEqual(extract_tags('#b #A #a #B #c'), ['b', 'a', 'c'])

    def test_underscore_and_digits_in_tag(self):
        self.assertEqual(extract_tags('#a_b #x1'), ['a_b', 'x1'])

    def test_lone_hash_is_not_a_tag(self):
        self.assertEqual(extract_tags('#'), [])
        self.assertEqual(extract_tags('a # b'), [])

    def test_numeric_tag_matches_per_contract(self):
        # Contract regex is #(\w+), so #123 is a tag (open question 1).
        self.assertEqual(extract_tags('#123'), ['123'])

    def test_trailing_punctuation_is_excluded(self):
        self.assertEqual(extract_tags('Go #flask, #web! (#py). #end?'),
                         ['flask', 'web', 'py', 'end'])

    def test_no_tags(self):
        self.assertEqual(extract_tags('nothing here'), [])
        self.assertEqual(extract_tags(''), [])


class TagModelCase(DbCase):
    def test_set_tags_replaces(self):
        u = self.make_user()
        p = self.make_post(u, 'x', tags=['a', 'b'])
        self.assertEqual([t.name for t in p.tags], ['a', 'b'])
        p.set_tags(['b', 'c'])
        db.session.commit()
        self.assertEqual([t.name for t in p.tags], ['b', 'c'])

    def test_set_tags_reuses_rows_and_lowercases(self):
        u = self.make_user()
        self.make_post(u, 'x', tags=['a'])
        self.make_post(u, 'y', tags=['A'])
        self.assertEqual(db.session.scalar(
            db.select(db.func.count()).select_from(Tag)), 1)

    def test_set_tags_empty_clears(self):
        u = self.make_user()
        p = self.make_post(u, 'x', tags=['a'])
        p.set_tags([])
        db.session.commit()
        self.assertEqual(p.tags, [])

    def test_posts_query_orders_newest_first(self):
        u = self.make_user()
        old = self.make_post(u, 'old #t', age=timedelta(days=2))
        new = self.make_post(u, 'new #t', age=timedelta(hours=1))
        mid = self.make_post(u, 'mid #t', age=timedelta(days=1))
        self.make_post(u, 'other #z')
        tag = db.session.scalar(db.select(Tag).where(Tag.name == 't'))
        self.assertEqual(db.session.scalars(tag.posts_query()).all(),
                         [new, mid, old])

    def test_to_dict(self):
        u = self.make_user()
        p = self.make_post(u, 'Hi #Flask #web')
        with self.app.test_request_context():
            d = p.to_dict()
        self.assertEqual(d['id'], p.id)
        self.assertEqual(d['body'], 'Hi #Flask #web')
        self.assertEqual(d['tags'], ['flask', 'web'])
        self.assertEqual(d['author'], u.id)
        self.assertTrue(d['timestamp'].endswith('+00:00'))
        self.assertEqual(
            datetime.fromisoformat(d['timestamp']).replace(tzinfo=None),
            p.timestamp)
        self.assertEqual(d['_links']['author'], f'/api/users/{u.id}')
        self.assertEqual(d['_links']['tags'],
                         {'flask': '/tag/flask', 'web': '/tag/web'})
        self.assertIn('language', d)


class TrendingCase(DbCase):
    def test_empty(self):
        self.assertEqual(trending_tags(), [])

    def test_window_boundary(self):
        u = self.make_user()
        # Timestamps are stored naive-UTC on SQLite; margins are small but
        # larger than any clock drift.
        self.make_post(u, 'in', age=timedelta(days=7) - timedelta(minutes=5),
                       tags=['inside'])
        self.make_post(u, 'out', age=timedelta(days=7) + timedelta(minutes=5),
                       tags=['outside'])
        self.make_post(u, 'fresh', tags=['fresh'])
        self.make_post(u, 'ancient', age=timedelta(days=30), tags=['ancient'])
        self.assertEqual(trending_tags(),
                         [('fresh', 1), ('inside', 1)])

    def test_window_boundary_is_not_shifted_by_hours(self):
        # A naive-local-time vs UTC mix-up would move the cutoff by hours.
        u = self.make_user()
        self.make_post(u, 'a', age=timedelta(days=6, hours=20), tags=['a'])
        self.make_post(u, 'b', age=timedelta(days=7, hours=4), tags=['b'])
        self.assertEqual(trending_tags(), [('a', 1)])

    def test_days_parameter(self):
        u = self.make_user()
        self.make_post(u, 'a', age=timedelta(days=2), tags=['a'])
        self.make_post(u, 'b', tags=['b'])
        self.assertEqual(trending_tags(days=1), [('b', 1)])
        self.assertEqual(trending_tags(days=3), [('a', 1), ('b', 1)])

    def test_tag_repeated_in_one_post_counts_once(self):
        u = self.make_user()
        self.make_post(u, '#x #X #x')
        self.assertEqual(trending_tags(), [('x', 1)])

    def test_counts_distinct_posts_and_orders_by_count(self):
        u = self.make_user()
        self.make_post(u, '#a #b')
        self.make_post(u, '#b')
        self.make_post(u, '#b #c')
        self.assertEqual(trending_tags(), [('b', 3), ('a', 1), ('c', 1)])

    def test_tie_broken_by_name(self):
        u = self.make_user()
        for name in ['zeta', 'alpha', 'mid']:
            self.make_post(u, '#' + name)
        self.assertEqual(trending_tags(),
                         [('alpha', 1), ('mid', 1), ('zeta', 1)])

    def test_limit(self):
        u = self.make_user()
        for i in range(7):
            self.make_post(u, f'#t{i}')
        self.make_post(u, '#t6')  # t6 has count 2 and must lead
        result = trending_tags()
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], ('t6', 2))
        self.assertEqual(len(trending_tags(limit=3)), 3)

    def test_index_box_renders(self):
        u = self.make_user()
        self.make_post(u, 'Hi #flask')
        self.make_post(u, 'Old #stale', age=timedelta(days=10))
        self.login()
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('Trending this week', html)
        # Isolate the box: the post list below it links #stale on its own.
        box = html.split('Trending this week')[1].split('<table')[0]
        self.assertIn('href="/tag/flask"', box)
        self.assertNotIn('/tag/stale', box)

    def test_index_box_with_no_tags(self):
        self.make_user()
        self.login()
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)
        self.assertIn('No trending tags yet', rv.get_data(as_text=True))


class TagWebCase(DbCase):
    def test_posting_creates_tags_and_links(self):
        self.make_user()
        self.login()
        rv = self.client.post('/index', data={'post': 'Hello #Flask #flask'},
                              follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        post = db.session.scalar(db.select(Post))
        self.assertEqual([t.name for t in post.tags], ['flask'])
        html = rv.get_data(as_text=True)
        self.assertIn('<a href="/tag/flask">#Flask</a>', html)
        self.assertIn('<a href="/tag/flask">#flask</a>', html)

    def test_tag_page_lists_only_tagged_posts(self):
        u = self.make_user()
        self.make_post(u, 'tagged #flask')
        self.make_post(u, 'untagged body')
        self.login()
        rv = self.client.get('/tag/Flask')
        self.assertEqual(rv.status_code, 200)
        html = rv.get_data(as_text=True)
        self.assertIn('tagged', html)
        self.assertNotIn('untagged body', html)

    def test_tag_page_404(self):
        self.make_user()
        self.login()
        self.assertEqual(self.client.get('/tag/nosuchtag').status_code, 404)

    def test_tag_page_requires_login(self):
        u = self.make_user()
        self.make_post(u, '#flask')
        rv = self.client.get('/tag/flask')
        self.assertEqual(rv.status_code, 302)
        self.assertIn('/auth/login', rv.headers['Location'])

    def test_tag_page_pagination(self):
        u = self.make_user()
        per_page = self.app.config['POSTS_PER_PAGE']
        for i in range(per_page + 1):
            self.make_post(u, f'post{i:03d} #flask',
                           age=timedelta(minutes=i))
        self.login()
        page1 = self.client.get('/tag/flask').get_data(as_text=True)
        self.assertIn('/tag/flask?page=2', page1)
        self.assertIn('post000', page1)
        self.assertNotIn(f'post{per_page:03d}', page1)
        page2 = self.client.get('/tag/flask?page=2').get_data(as_text=True)
        self.assertIn(f'post{per_page:03d}', page2)
        self.assertNotIn('post000', page2)
        self.assertIn('/tag/flask?page=1', page2)
        self.assertNotIn('?page=3', page2)

    def test_tag_page_out_of_range_page_is_not_an_error(self):
        u = self.make_user()
        self.make_post(u, '#flask')
        self.login()
        self.assertEqual(self.client.get('/tag/flask?page=99').status_code,
                         200)

    def test_body_is_escaped_and_only_tag_is_linked(self):
        u = self.make_user()
        self.make_post(u, '<script>alert(1)</script> #x')
        self.login()
        html = self.client.get('/tag/x').get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertIn('<a href="/tag/x">#x</a>', html)

    def test_tag_links_respect_proxy_prefix(self):
        u = self.make_user()
        self.make_post(u, '#flask')
        self.login()
        html = self.client.get('/absproxy/5001/tag/flask').get_data(
            as_text=True)
        self.assertIn('href="/absproxy/5001/tag/flask"', html)


class TagApiCase(DbCase):
    def get_token(self, username='john', password='cat'):
        from base64 import b64encode
        creds = b64encode(f'{username}:{password}'.encode()).decode()
        rv = self.client.post('/api/tokens',
                              headers={'Authorization': 'Basic ' + creds})
        self.assertEqual(rv.status_code, 200)
        return rv.get_json()['token']

    def auth(self, token):
        return {'Authorization': 'Bearer ' + token}

    def test_token_flow_and_collection_shape(self):
        u = self.make_user()
        self.make_post(u, 'Hi #Flask', age=timedelta(hours=1))
        token = self.get_token()
        rv = self.client.get('/api/tags/flask/posts',
                             headers=self.auth(token))
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(set(data), {'items', '_meta', '_links'})
        self.assertEqual(data['_meta'], {'page': 1, 'per_page': 10,
                                         'total_pages': 1, 'total_items': 1})
        self.assertEqual(len(data['items']), 1)
        item = data['items'][0]
        self.assertEqual(item['body'], 'Hi #Flask')
        self.assertEqual(item['tags'], ['flask'])
        self.assertEqual(item['author'], u.id)
        self.assertIsNone(data['_links']['next'])
        self.assertIsNone(data['_links']['prev'])

    def test_name_is_case_insensitive(self):
        u = self.make_user()
        self.make_post(u, '#flask')
        token = self.get_token()
        rv = self.client.get('/api/tags/FLASK/posts',
                             headers=self.auth(token))
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()['_meta']['total_items'], 1)

    def test_pagination_links(self):
        u = self.make_user()
        for i in range(5):
            self.make_post(u, f'p{i} #t', age=timedelta(minutes=i))
        h = self.auth(self.get_token())
        rv = self.client.get('/api/tags/t/posts?per_page=2', headers=h)
        data = rv.get_json()
        self.assertEqual([i['body'] for i in data['items']],
                         ['p0 #t', 'p1 #t'])
        self.assertEqual(data['_meta']['total_items'], 5)
        self.assertEqual(data['_meta']['total_pages'], 3)
        self.assertIsNone(data['_links']['prev'])
        rv = self.client.get(data['_links']['next'], headers=h)
        data = rv.get_json()
        self.assertEqual([i['body'] for i in data['items']],
                         ['p2 #t', 'p3 #t'])
        self.assertIsNotNone(data['_links']['prev'])
        rv = self.client.get(data['_links']['next'], headers=h)
        data = rv.get_json()
        self.assertEqual([i['body'] for i in data['items']], ['p4 #t'])
        self.assertIsNone(data['_links']['next'])

    def test_per_page_is_capped_at_100(self):
        u = self.make_user()
        self.make_post(u, '#t')
        rv = self.client.get('/api/tags/t/posts?per_page=1000',
                             headers=self.auth(self.get_token()))
        self.assertEqual(rv.get_json()['_meta']['per_page'], 100)

    def test_unknown_tag_is_json_404(self):
        self.make_user()
        rv = self.client.get('/api/tags/nosuchtag/posts',
                             headers=self.auth(self.get_token()))
        self.assertEqual(rv.status_code, 404)
        self.assertIn('error', rv.get_json())

    def test_missing_token_is_json_401(self):
        u = self.make_user()
        self.make_post(u, '#flask')
        rv = self.client.get('/api/tags/flask/posts')
        self.assertEqual(rv.status_code, 401)
        self.assertIn('error', rv.get_json())

    def test_bad_token_is_401(self):
        rv = self.client.get('/api/tags/flask/posts',
                             headers=self.auth('bogus'))
        self.assertEqual(rv.status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
