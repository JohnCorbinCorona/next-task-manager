"""Run: python -m streamlit run app.py"""
import csv
from datetime import date
import io
import os
from urllib.parse import urlparse
import streamlit as st
from storage import Store, PRIORITIES

st.set_page_config(page_title='Next • Task Manager', page_icon='✅', layout='wide')
st.markdown('''<style>
.block-container {max-width:1180px;padding-top:4rem;}
h1 {letter-spacing:-.045em;}
[data-testid="stMetric"] {background:#142b45;color:white;padding:1.2rem;border-radius:14px;}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:white;}
[data-testid="stForm"] {border-radius:14px;background:transparent;}
button[kind="primaryFormSubmit"], button[kind="primary"] {background:#087f6d;border-color:#087f6d;color:white;}
</style>''', unsafe_allow_html=True)

# Streamlit's secrets are supplied by the app owner, never by visitors.
database_url = os.environ.get('DATABASE_URL', '')
if not database_url:
    try:
        database_url = st.secrets.get('DATABASE_URL', '')
    except FileNotFoundError:
        pass
hostname = urlparse(st.context.url).hostname or ''
if hostname.endswith('.streamlit.app') and not database_url:
    st.title('Next • Task Manager')
    st.info('This app is awaiting its persistent database connection. Account creation opens once setup is complete.')
    st.stop()

store = Store(database_url)
try:
    store.initialize()
except Exception:
    st.error('The task database is unavailable. Please try again later. No changes were saved.')
    st.stop()


def logout():
    for key in list(st.session_state):
        del st.session_state[key]


def flash(message):
    st.session_state['notice'] = message


if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))

if not st.session_state.get('username'):
    st.caption('NEXT / PERSONAL TASK MANAGER')
    st.title('A little focus. A lot done.')
    st.write('Your tasks, priorities, and progress in one place.')
    login_tab, register_tab = st.tabs(['Sign in', 'Create an account'])
    with login_tab:
        with st.form('login', clear_on_submit=True):
            username = st.text_input('Username', max_chars=32)
            password = st.text_input('Password', type='password', max_chars=128)
            login = st.form_submit_button('Sign in', type='primary', width='stretch')
        if login:
            try:
                authenticated = store.login(username, password)
                if authenticated:
                    logout()
                    st.session_state['username'] = authenticated
                    st.rerun()
                else:
                    st.error('Sign-in failed. Check your username and password. After five failed attempts, wait one minute.')
            except Exception:
                st.error('Sign-in is temporarily unavailable. Please try again.')
    with register_tab:
        with st.form('register', clear_on_submit=True):
            new_username = st.text_input('Choose a username', max_chars=32, help='3–32 letters, numbers, or underscores.')
            new_password = st.text_input('Choose a password', type='password', max_chars=128, help='At least eight characters.')
            confirmation = st.text_input('Repeat your password', type='password', max_chars=128)
            register = st.form_submit_button('Create account', type='primary', width='stretch')
        if register:
            if new_password != confirmation:
                st.error('The passwords do not match.')
            else:
                try:
                    store.register(new_username, new_password)
                    st.success('Account created. Open Sign in to get started.')
                except ValueError as error:
                    st.error(str(error))
                except Exception:
                    st.error('Your account could not be saved. Please try again.')
    st.caption('Accounts and tasks are saved automatically. Your terminal-project accounts are separate; create a new account here.')
    st.stop()

owner = st.session_state['username']
with st.sidebar:
    st.title('✅ Next')
    st.caption(f'Signed in as {owner}')
    st.button('Log out', on_click=logout, width='stretch')
    st.divider()
    status_filter = st.radio('Show tasks', ['All', 'Pending', 'Completed'])
    priority_filter = st.selectbox('Priority', ['All', *PRIORITIES])
    search = st.text_input('Search tasks', max_chars=100, placeholder='Find a task…')

try:
    tasks = store.list_tasks(owner)
except Exception:
    st.error('Your tasks could not be loaded. Please try again later.')
    st.stop()

today = date.today().isoformat()
pending = sum(task['status'] == 'Pending' for task in tasks)
completed = len(tasks) - pending
overdue = sum(task['status'] == 'Pending' and bool(task['due_date']) and task['due_date'] < today for task in tasks)
st.caption('YOUR PERSONAL WORKSPACE')
st.title('What’s next?')
st.write('Make a plan. Take the next step.')
a, b, c = st.columns(3)
a.metric('Pending', pending)
b.metric('Completed', completed)
c.metric('Overdue', overdue)
if tasks:
    st.progress(completed / len(tasks), text=f'{completed} of {len(tasks)} tasks completed')

with st.expander('＋ Add a task', expanded=True):
    with st.form(f"add-{st.session_state.get('version', 0)}"):
        description = st.text_input('Task description', max_chars=300, placeholder='What do you want to get done?')
        first, second = st.columns(2)
        priority = first.selectbox('Task priority', list(PRIORITIES), index=1)
        due = second.date_input('Due date (optional)', value=None)
        add = st.form_submit_button('Add task', type='primary')
    if add:
        try:
            store.add_task(owner, description, priority, due.isoformat() if due else None)
            st.session_state['version'] = st.session_state.get('version', 0) + 1
            flash('Task added and saved.')
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        except Exception:
            st.error('The task could not be saved. Please try again.')

visible = [task for task in tasks
           if (status_filter == 'All' or task['status'] == status_filter)
           and (priority_filter == 'All' or task['priority'] == priority_filter)
           and search.casefold() in task['description'].casefold()]
visible.sort(key=lambda task: (task['status'] == 'Completed', task['due_date'] or '9999-12-31',
                               {'High':0, 'Medium':1, 'Low':2}[task['priority']]))
st.subheader('Your tasks')
if not tasks:
    st.info('Your list is clear. Add your first task above.')
elif not visible:
    st.info('No tasks match these filters.')
else:
    st.caption(f'{len(visible)} shown • Tasks with due dates appear first')
    for task in visible:
        identifier = task['id']
        with st.container(border=True):
            content, action = st.columns([4, 1])
            # st.text keeps user-entered task content literal, not HTML or Markdown.
            content.text(task['description'])
            details = f"{task['status']} · {task['priority']} priority"
            if task['due_date']:
                details += f" · Due {task['due_date']}"
                if task['status'] == 'Pending' and task['due_date'] < today:
                    details += ' · OVERDUE'
            content.caption(details)
            target_status = 'Completed' if task['status'] == 'Pending' else 'Pending'
            if action.button('Complete' if target_status == 'Completed' else 'Reopen', key=f'complete-{identifier}', width='stretch'):
                try:
                    if store.set_status(owner, identifier, target_status):
                        flash('Task updated and saved.')
                    else:
                        flash('That task no longer exists. Your list was refreshed.')
                    st.rerun()
                except Exception:
                    st.error('Could not update the task. Please try again.')
            if action.button('Delete', key=f'delete-{identifier}', width='stretch'):
                st.session_state['delete_id'] = identifier
            if st.session_state.get('delete_id') == identifier:
                st.warning('Delete this task permanently?')
                confirm, cancel = st.columns(2)
                if confirm.button('Confirm delete', key=f'confirm-{identifier}'):
                    try:
                        store.delete_task(owner, identifier)
                        del st.session_state['delete_id']
                        flash('Task deleted.')
                        st.rerun()
                    except Exception:
                        st.error('Could not delete the task. Please try again.')
                if cancel.button('Cancel', key=f'cancel-{identifier}'):
                    del st.session_state['delete_id']
                    st.rerun()

buffer = io.StringIO()
writer = csv.DictWriter(buffer, fieldnames=['id', 'description', 'priority', 'due_date', 'status'])
writer.writeheader()
for task in tasks:
    writer.writerow({key: task[key] for key in writer.fieldnames})
with st.sidebar:
    st.divider()
    st.download_button('Download my tasks', buffer.getvalue(), file_name='my_tasks.csv', mime='text/csv', on_click='ignore', width='stretch')
    st.caption('Changes save immediately. Logging out does not delete your tasks.')
st.caption('Built with Python and Streamlit • Saved automatically • Every account has its own task list')
