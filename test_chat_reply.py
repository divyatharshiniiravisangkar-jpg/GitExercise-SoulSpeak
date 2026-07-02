import unittest

from app import app, db, User, Chat, Diary, Post


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

    def test_post_token_prevents_duplicate_post_submit(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True
            session['post_tokens'] = ['one-time-token']

        data = {
            'content': 'One photo post',
            'post_token': 'one-time-token'
        }

        first_response = self.client.post('/post', data=data, follow_redirects=False)
        second_response = self.client.post('/post', data=data, follow_redirects=False)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(Post.query.filter_by(content='One photo post').count(), 1)

    def test_admin_chat_shows_user_picker_and_selected_thread(self):
        bob = User(username='bob', email='bob@example.com', password='pw')
        db.session.add(bob)
        db.session.commit()

        alice_message = Chat(
            message='Alice needs help',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        bob_message = Chat(
            message='Bob needs help',
            sender=bob.username,
            user_id=bob.id,
            recipient='Admin'
        )
        db.session.add_all([alice_message, bob_message])
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.get(f'/chat?user_id={bob.id}')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('bob@example.com', page)
        self.assertIn('Bob needs help', page)
        self.assertNotIn('Alice needs help', page)

    def test_admin_chat_does_not_auto_open_a_user_thread(self):
        message = Chat(
            message='Alice needs help',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        db.session.add(message)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.get('/chat')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Select a user to read chats.', page)
        self.assertIn('alice@example.com', page)
        self.assertNotIn('Alice needs help', page)

    def test_admin_direct_message_targets_selected_user(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.post(
            '/chat',
            data={
                'selected_user_id': self.user.id,
                'message': 'Admin answer'
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        message = Chat.query.filter_by(message='Admin answer').one()
        self.assertEqual(message.sender, 'Admin')
        self.assertEqual(message.user_id, self.user.id)
        self.assertEqual(message.recipient, self.user.username)

    def test_user_can_delete_own_chat_message(self):
        message = Chat(
            message='Wrong chat',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        db.session.add(message)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True

        response = self.client.post(f'/chat/{message.id}/delete', follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Chat.query.get(message.id))

    def test_admin_delete_original_chat_removes_replies(self):
        original = Chat(
            message='Start thread',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        db.session.add(original)
        db.session.commit()

        reply = Chat(
            message='Reply thread',
            sender='Admin',
            user_id=self.user.id,
            recipient=self.user.username,
            reply_to=original.id
        )
        db.session.add(reply)
        db.session.commit()
        original_id = original.id
        reply_id = reply.id

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.post(f'/chat/{original_id}/delete', follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Chat.query.get(original_id))
        self.assertIsNone(Chat.query.get(reply_id))

    def test_user_can_delete_own_diary_entry(self):
        entry = Diary(content='Wrong diary', user_id=self.user.id)
        db.session.add(entry)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True

        response = self.client.post(f'/diary/{entry.id}/delete', follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Diary.query.get(entry.id))

    def test_admin_cannot_view_user_diary_entries(self):
        entry = Diary(content='Alice private thought', user_id=self.user.id)
        db.session.add(entry)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.get('/diary')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Diary Users', page)
        self.assertIn('alice', page)
        self.assertNotIn('Alice private thought', page)
        self.assertNotIn('Write your diary entry', page)
        self.assertNotIn('Save Entry', page)

    def test_admin_cannot_delete_user_diary_entry(self):
        entry = Diary(content='Alice private thought', user_id=self.user.id)
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.post(f'/diary/{entry_id}/delete', follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(Diary.query.get(entry_id))

    def test_admin_database_does_not_show_diary_entries(self):
        entry = Diary(content='Alice private thought', user_id=self.user.id)
        db.session.add(entry)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.get('/database')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Diary Users', response.data)
        self.assertIn(b'alice', response.data)
        self.assertNotIn(b'Alice private thought', response.data)

    def test_admin_database_links_chat_users_without_showing_messages(self):
        message = Chat(
            message='Alice needs help',
            sender=self.user.username,
            user_id=self.user.id,
            recipient='Admin'
        )
        db.session.add(message)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

        response = self.client.get('/database')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Chat Users', page)
        self.assertIn(f'/chat?user_id={self.user.id}', page)
        self.assertNotIn('Alice needs help', page)


if __name__ == '__main__':
    unittest.main()
