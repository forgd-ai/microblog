#!/usr/bin/env python
from datetime import datetime, timezone, timedelta
import unittest
import sqlalchemy as sa
from app import create_app, db
from app.models import User, Post
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


# The hashtag tests import parse_tags and Tag inside each test, not at the top
# of the file, so that before they exist only these tests fail, not the suite.

class TagParseCase(unittest.TestCase):
    def test_finds_tags_lower_cased(self):
        from app.models import parse_tags
        self.assertEqual(parse_tags('I like #Python and #python_3'),
                         ['python', 'python_3'])

    def test_repeated_tag_once(self):
        from app.models import parse_tags
        self.assertEqual(parse_tags('#a #A #a'), ['a'])

    def test_no_tags(self):
        from app.models import parse_tags
        self.assertEqual(parse_tags('no tags here'), [])


class TagStorageCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def add_post(self, body, author):
        post = Post(body=body, author=author)
        db.session.add(post)
        post.add_tags_from_body()
        db.session.commit()
        return post

    def test_tags_stored_once_and_reused(self):
        from app.models import Tag
        u = User(username='susan', email='susan@example.com')
        db.session.add(u)
        db.session.commit()
        p1 = self.add_post('#x #X', u)
        p1_tags = db.session.scalars(p1.tags.select()).all()
        self.assertEqual([t.name for t in p1_tags], ['x'])
        p2 = self.add_post('more #x', u)
        p2_tags = db.session.scalars(p2.tags.select()).all()
        self.assertEqual([t.id for t in p2_tags], [p1_tags[0].id])
        self.assertEqual(
            db.session.scalar(sa.select(sa.func.count()).select_from(Tag)), 1)


class TagAPICase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        user = User(username='susan', email='susan@example.com')
        db.session.add(user)
        db.session.commit()
        self.token = user.get_token()
        self.post = Post(body='#Python', author=user)
        db.session.add(self.post)
        self.post.add_tags_from_body()
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get_tag_posts(self):
        rv = self.client.get('/api/tags/python/posts', headers={
            'Authorization': f'Bearer {self.token}'})
        self.assertEqual(rv.status_code, 200)
        self.assertIn(self.post.id, [p['id'] for p in rv.json['items']])
        self.assertEqual(rv.json['_meta'], {'page': 1, 'per_page': 10,
                                            'total_pages': 1,
                                            'total_items': 1})

    def test_get_tag_posts_requires_token(self):
        rv = self.client.get('/api/tags/python/posts')
        self.assertEqual(rv.status_code, 401)
        self.assertEqual(rv.json, {'error': 'Unauthorized'})


class TokenApiCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        u = User(username='svc', email='svc@example.com')
        u.set_password('secret')
        db.session.add(u)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _new_token(self):
        rv = self.client.post('/api/tokens', auth=('svc', 'secret'))
        self.assertEqual(rv.status_code, 200)
        return rv.get_json()['token']

    def _bearer(self, token):
        return {'Authorization': f'Bearer {token}'}

    def test_reauth_after_revoke_gives_working_token(self):
        old = self._new_token()
        rv = self.client.delete('/api/tokens', headers=self._bearer(old))
        self.assertEqual(rv.status_code, 204)
        token = self._new_token()
        rv = self.client.get('/api/users', headers=self._bearer(token))
        self.assertEqual(rv.status_code, 200)

    def test_second_login_does_not_invalidate_first_token(self):
        first = self._new_token()
        self._new_token()
        rv = self.client.get('/api/users', headers=self._bearer(first))
        self.assertEqual(rv.status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
