# Next — Personal Task Manager

Live app: https://johncorbin-next.streamlit.app/

A Streamlit task manager with registration, sign-in, private task lists, completion/reopening, confirmed deletion, priorities, due dates, filters, and CSV export.

## Run locally

Keep these files together. In PyCharm's Terminal, from this folder:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Use `python3` if needed. Run with Streamlit rather than PyCharm's ordinary Run Python button. Create a new account; your original terminal-project accounts are separate.

Accounts and tasks save in `task_manager.db` beside storage.py. Keep that file for future visits. It is excluded from GitHub. The original Task_Manager.py assignment is unchanged.

## Publish on Streamlit Community Cloud

The GitHub repository contains code, not account records. Durable public hosting needs an external PostgreSQL database: Streamlit Community Cloud does not guarantee local SQLite files persist.

1. Provision a PostgreSQL database with a provider of your choice. Review its current plan and limits.
2. Keep the connection URL private. In Streamlit's app secrets, set:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
```

3. Deploy this repository's `main` branch with `app.py` as the main file, using Python 3.12 or newer.
4. The app creates its tables automatically. The database account needs permission to create and modify its own tables.
5. Verify registration, login, and saved tasks after a server restart before sharing the public URL.

Without DATABASE_URL, local use defaults to SQLite. On a streamlit.app hostname, the app stops at a setup message rather than storing accounts in temporary local storage. Back up the hosted database with your provider. SQLite and PostgreSQL data are separate; this app does not migrate existing accounts automatically.

Official storage guidance: https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
Secrets: https://docs.streamlit.io/deploy/concepts/secrets

## Learn the pieces

- `app.py`: forms, session state, task cards, filters, and feedback.
- `storage.py`: validation, password verification, database queries, and task ownership checks.
- `test_app.py` and `test_storage.py`: reproducible checks using temporary databases.
- Each database mutation commits immediately; logout only ends the session.
- Every list/update/delete query includes the logged-in username.
- Passwords use a random per-account salt and PBKDF2-HMAC-SHA256 with 600,000 iterations. Password text is not stored.
- SQL values are bound parameters rather than concatenated into query text.
- Five failed sign-ins lock that account for one minute. This basic account throttle is not a substitute for infrastructure-level abuse controls.

## Tests

```sh
python -m unittest discover -v
```

The supplied tests cover the SQLite backend and Streamlit interactions. PostgreSQL support uses psycopg and must also be integration-tested against the configured database before public use; no cloud database is bundled.

## Scope

This is a learning/portfolio application, not an enterprise identity platform. There is no password recovery, email verification, or multifactor authentication. Database administrators can access stored task data; account separation in the app is not encryption from the host. Do not publish credentials, task databases, or real account files. Avoid putting sensitive data in demo tasks.

Keep your original terminal Python file for the course submission unless your instructor accepts the web version.
