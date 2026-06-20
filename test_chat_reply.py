import unittest

from app import app, db, User, Chat


class ChatReplyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            WTF_CSRF_ENABLED=False,
            SECRET_KEY='test-secret'
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(username='alice', email='alice@example.com', password='pw')
        self.admin = User(username='Admin', email='admin@example.com', password='pw')
        db.session.add_all([self.user, self.admin])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_reply_message_stores_only_reply_text(self):
        original = Chat(
            message='Hello there',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        db.session.add(original)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.post(
            '/chat',
            data={
                'reply_to': original.id,
                'reply_message': 'I am replying now'
            },
            follow_redirects=True
        )

        self.assertEqual(response.status_code, 200)

        replies = Chat.query.filter_by(reply_to=original.id).all()
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].message, 'I am replying now')
        self.assertNotIn('Hello there', replies[0].message)


if __name__ == '__main__':
    unittest.main()
