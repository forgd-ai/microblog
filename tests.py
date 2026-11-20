#!/usr/bin/env python
from datetime import datetime, timezone, timedelta
import unittest
import sqlalchemy as sa
from app import create_app, db
from app.models import User, Post, Tag
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None


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


class HashtagCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        self.user = User(username='susan', email='susan@example.com')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def make_post(self, body, age=timedelta()):
        post = Post(body=body, author=self.user,
                    timestamp=datetime.now(timezone.utc) - age)
        db.session.add(post)
        post.set_tags_from_body()
        db.session.commit()
        return post

    def login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    def test_parse_tags(self):
        self.assertEqual(Post.parse_tags('#Flask and #flask #SQL_2'),
                         ['flask', 'sql_2'])
        self.assertEqual(Post.parse_tags('a#b &#39; # none'), [])
        self.assertEqual(Post.parse_tags('(#one),#two'), ['one', 'two'])

    def test_tags_are_shared_between_posts(self):
        p1 = self.make_post('hello #python')
        p2 = self.make_post('more #Python and #flask')
        self.assertEqual([t.name for t in p1.tags], ['python'])
        self.assertEqual(sorted(t.name for t in p2.tags),
                         ['flask', 'python'])
        self.assertEqual(db.session.scalar(
            sa.select(sa.func.count()).select_from(Tag)), 2)

    def test_trending_orders_limits_and_windows(self):
        for name, uses in [('a', 1), ('b', 4), ('c', 3), ('d', 2),
                           ('e', 2), ('f', 1)]:
            for _ in range(uses):
                self.make_post('#' + name)
        for _ in range(9):
            self.make_post('#old', age=timedelta(days=8))
        trending = [(tag.name, uses) for tag, uses in Tag.trending()]
        self.assertEqual(trending, [('b', 4), ('c', 3), ('d', 2), ('e', 2),
                                    ('a', 1)])

    def test_tag_page_lists_posts(self):
        self.make_post('first #demo')
        self.make_post('no tags here')
        self.make_post('second #Demo')
        self.login()
        rv = self.client.get('/tag/demo')
        self.assertEqual(rv.status_code, 200)
        html = rv.get_data(as_text=True)
        self.assertIn('first', html)
        self.assertIn('second', html)
        self.assertNotIn('no tags here', html)
        self.assertLess(html.index('second'), html.index('first'))

    def test_tag_page_unknown_tag_is_404(self):
        self.login()
        self.assertEqual(self.client.get('/tag/missing').status_code, 404)

    def test_post_body_links_tags_and_escapes(self):
        self.make_post('<b>hi</b> #News')
        self.login()
        html = self.client.get('/tag/news').get_data(as_text=True)
        self.assertIn('<a href="/tag/news">#News</a>', html)
        self.assertIn('&lt;b&gt;hi&lt;/b&gt;', html)
        self.assertNotIn('<b>hi</b>', html)

    def test_index_shows_trending_box(self):
        self.make_post('#hot #hot2')
        self.make_post('#hot')
        self.login()
        html = self.client.get('/index').get_data(as_text=True)
        self.assertIn('Trending this week', html)
        self.assertLess(html.index('#hot<'), html.index('#hot2<'))

    def test_creating_a_post_stores_tags(self):
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.login()
        rv = self.client.post('/index', data={'post': 'web #Created'})
        self.assertEqual(rv.status_code, 302)
        post = db.session.scalar(sa.select(Post))
        self.assertEqual([t.name for t in post.tags], ['created'])

    def test_api_tag_posts(self):
        for i in range(3):
            self.make_post('post {} #api'.format(i))
        token = self.user.get_token()
        db.session.commit()
        headers = {'Authorization': 'Bearer ' + token}
        rv = self.client.get('/api/tags/API/posts?per_page=2',
                             headers=headers)
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['items'][0]['body'], 'post 2 #api')
        self.assertEqual(data['items'][0]['tags'], ['api'])
        self.assertEqual(data['items'][0]['author'], 'susan')
        self.assertEqual(data['_meta']['total_items'], 3)
        self.assertIsNotNone(data['_links']['next'])
        self.assertIsNone(data['_links']['prev'])

    def test_api_tag_posts_errors(self):
        self.assertEqual(self.client.get('/api/tags/x/posts').status_code,
                         401)
        token = self.user.get_token()
        db.session.commit()
        rv = self.client.get('/api/tags/missing/posts',
                             headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(rv.status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
