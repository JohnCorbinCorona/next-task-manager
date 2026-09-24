"""Database and account logic. Every task query is restricted to its owner."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

ITERATIONS = 600_000
PRIORITIES = ('Low', 'Medium', 'High')
STATUSES = ('Pending', 'Completed')

class Store:
    def __init__(self, database_url='', sqlite_path=None):
        self.database_url = database_url
        self.path = Path(sqlite_path or os.environ.get('TASK_DB_PATH') or Path(__file__).with_name('task_manager.db'))
        self.postgres = bool(database_url)

    @contextmanager
    def connect(self):
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            connection = psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10)
        else:
            connection = sqlite3.connect(self.path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def query(self, connection, sql, params=()):
        # Only developer-authored SQL reaches here; values remain bound parameters.
        return connection.execute(sql.replace('?', '%s') if self.postgres else sql, params)

    def initialize(self):
        with self.connect() as connection:
            self.query(connection, '''CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                iterations INTEGER NOT NULL, failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until BIGINT NOT NULL DEFAULT 0)''')
            self.query(connection, '''CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(username),
                description TEXT NOT NULL, priority TEXT NOT NULL,
                due_date TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL)''')
            self.query(connection, 'CREATE INDEX IF NOT EXISTS tasks_owner ON tasks(owner)')

    @staticmethod
    def normalize_username(username):
        return username.strip().lower()

    @staticmethod
    def hash_password(password, salt, iterations=ITERATIONS):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), iterations).hex()

    def register(self, username, password):
        username = self.normalize_username(username)
        if not re.fullmatch(r'[a-z0-9_]{3,32}', username):
            raise ValueError('Use 3–32 letters, numbers, or underscores for your username.')
        if not 8 <= len(password) <= 128 or not password.strip():
            raise ValueError('Choose a password between 8 and 128 characters, not just spaces.')
        salt = secrets.token_hex(16)
        password_hash = self.hash_password(password, salt)
        with self.connect() as connection:
            result = self.query(connection, '''INSERT INTO accounts
                (username, salt, password_hash, iterations) VALUES (?, ?, ?, ?)
                ON CONFLICT (username) DO NOTHING''', (username, salt, password_hash, ITERATIONS))
            if result.rowcount != 1:
                raise ValueError('That username is already taken.')
        return username

    def login(self, username, password):
        username = self.normalize_username(username)
        if len(username) > 32 or len(password) > 128:
            return None
        with self.connect() as connection:
            if not self.postgres:
                connection.execute('BEGIN IMMEDIATE')
            suffix = ' FOR UPDATE' if self.postgres else ''
            account = self.query(connection, 'SELECT * FROM accounts WHERE username = ?' + suffix, (username,)).fetchone()
            # Unknown accounts still perform a hash rather than returning immediately.
            salt = account['salt'] if account else '00' * 16
            iterations = account['iterations'] if account else ITERATIONS
            candidate = self.hash_password(password, salt, iterations)
            now = int(time.time())
            if not account or account['locked_until'] > now:
                return None
            if hmac.compare_digest(candidate, account['password_hash']):
                self.query(connection, 'UPDATE accounts SET failed_attempts = 0, locked_until = 0 WHERE username = ?', (username,))
                return username
            failures = (0 if account['locked_until'] else account['failed_attempts']) + 1
            lock_until = now + 60 if failures >= 5 else 0
            self.query(connection, 'UPDATE accounts SET failed_attempts = ?, locked_until = ? WHERE username = ?',
                       (failures, lock_until, username))
        return None

    def list_tasks(self, owner):
        with self.connect() as connection:
            rows = self.query(connection, 'SELECT * FROM tasks WHERE owner = ? ORDER BY created_at DESC, id', (owner,)).fetchall()
            return [dict(row) for row in rows]

    def add_task(self, owner, description, priority='Medium', due_date=None):
        description = description.strip()
        if not 1 <= len(description) <= 300:
            raise ValueError('Enter a task description between 1 and 300 characters.')
        if priority not in PRIORITIES:
            raise ValueError('Choose Low, Medium, or High priority.')
        if due_date:
            try:
                parsed = date.fromisoformat(due_date)
                if parsed.isoformat() != due_date:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError('Choose a valid due date.') from None
        identifier = uuid.uuid4().hex
        with self.connect() as connection:
            self.query(connection, '''INSERT INTO tasks
                (id, owner, description, priority, due_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (identifier, owner, description, priority, due_date or None, 'Pending', datetime.now(timezone.utc).isoformat()))
        return identifier

    def set_status(self, owner, task_id, status):
        if status not in STATUSES:
            raise ValueError('Invalid task status.')
        with self.connect() as connection:
            return self.query(connection, 'UPDATE tasks SET status = ? WHERE id = ? AND owner = ?',
                              (status, task_id, owner)).rowcount == 1

    def delete_task(self, owner, task_id):
        with self.connect() as connection:
            return self.query(connection, 'DELETE FROM tasks WHERE id = ? AND owner = ?', (task_id, owner)).rowcount == 1
