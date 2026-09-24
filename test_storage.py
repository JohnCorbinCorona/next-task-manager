from pathlib import Path
import tempfile
import unittest
from storage import Store

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(sqlite_path=Path(self.temp.name)/'test.db')
        self.store.initialize()
        self.store.register('Alice', 'practice-one')
        self.store.register('bob', 'practice-two')

    def tearDown(self):
        self.temp.cleanup()

    def test_authentication_and_throttle(self):
        self.assertEqual(self.store.login(' ALICE ', 'practice-one'), 'alice')
        self.assertIsNone(self.store.login('missing', 'practice-one'))
        for _ in range(5):
            self.assertIsNone(self.store.login('alice', 'wrong'))
        self.assertIsNone(self.store.login('alice', 'practice-one'))
        with self.store.connect() as connection:
            connection.execute('UPDATE accounts SET locked_until = 1 WHERE username = ?', ('alice',))
        self.assertEqual(self.store.login('alice', 'practice-one'), 'alice')
        with self.assertRaises(ValueError):
            self.store.register('ALICE', 'another-password')

    def test_ownership_and_persistence(self):
        task = self.store.add_task('alice', 'Study functions', 'High', '2026-09-24')
        self.assertFalse(self.store.list_tasks('bob'))
        self.assertFalse(self.store.set_status('bob', task, 'Completed'))
        self.assertFalse(self.store.delete_task('bob', task))
        self.assertTrue(self.store.set_status('alice', task, 'Completed'))
        restarted = Store(sqlite_path=self.store.path)
        self.assertEqual(restarted.list_tasks('alice')[0]['status'], 'Completed')
        self.assertTrue(self.store.set_status('alice', task, 'Pending'))
        self.assertTrue(self.store.delete_task('alice', task))
        self.assertFalse(restarted.list_tasks('alice'))

    def test_validation_and_safe_queries(self):
        for username, password in [('ab','long-password'), ('../bad','long-password'), ('valid','short')]:
            with self.assertRaises(ValueError):
                self.store.register(username,password)
        for text, priority, due in [('', 'Medium', None), ('task','Urgent',None), ('task','High','2026-02-30')]:
            with self.assertRaises(ValueError):
                self.store.add_task('alice',text,priority,due)
        self.store.add_task('alice', "Robert'); DROP TABLE tasks;--")
        self.assertEqual(len(self.store.list_tasks('alice')),1)
        with self.store.connect() as connection:
            account=connection.execute('SELECT * FROM accounts WHERE username = ?',('alice',)).fetchone()
            self.assertEqual(len(account['salt']),32)
            self.assertEqual(len(account['password_hash']),64)
            self.assertNotIn('practice-one',str(dict(account)))

if __name__=='__main__':
    unittest.main()
