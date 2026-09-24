import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP=Path(__file__).with_name('app.py')
def item(elements,label):
    return next(element for element in elements if element.label == label)

class InterfaceTests(unittest.TestCase):
    def test_full_user_flow(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'TASK_DB_PATH':str(Path(folder)/'test.db'), 'DATABASE_URL':''}):
            app=AppTest.from_file(str(APP),default_timeout=30).run()
            self.assertFalse(app.exception)
            item(app.text_input,'Choose a username').input('alice')
            item(app.text_input,'Choose a password').input('practice-one')
            item(app.text_input,'Repeat your password').input('practice-one')
            item(app.button,'Create account').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            item(app.text_input,'Username').input('alice')
            item(app.text_input,'Password').input('wrong')
            item(app.button,'Sign in').click().run()
            self.assertTrue(app.error)
            item(app.text_input,'Username').input('alice')
            item(app.text_input,'Password').input('practice-one')
            item(app.button,'Sign in').click().run()
            self.assertFalse(app.exception)
            item(app.text_input,'Task description').input('Learn Python')
            item(app.button,'Add task').click().run()
            self.assertEqual(app.metric[0].value,'1')
            item(app.button,'Complete').click().run()
            self.assertEqual(app.metric[1].value,'1')
            item(app.button,'Reopen').click().run()
            self.assertEqual(app.metric[0].value,'1')
            item(app.button,'Delete').click().run()
            item(app.button,'Cancel').click().run()
            self.assertEqual(app.metric[0].value,'1')
            item(app.button,'Delete').click().run()
            item(app.button,'Confirm delete').click().run()
            self.assertEqual(app.metric[0].value,'0')
            item(app.button,'Log out').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(button.label=='Sign in' for button in app.button))
            self.assertNotIn('username', app.session_state)

if __name__=='__main__':
    unittest.main()
