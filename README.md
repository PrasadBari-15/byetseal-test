# Product Testing App (Flask)

A minimal web app to record product testing results (like your paper log) with login and Excel export.

## Quick start
```bash
python -m venv .venv
. .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# open http://localhost:5000
```
Login with:
- username: `admin`
- password: `admin123`

## Features
- Login / logout, admin user creation
- New Test form matching your notebook columns
- List + filter tests by date
- Export filtered list to Excel (.xlsx)
- SQLite by default (set `DATABASE_URL` env var to use MySQL or Postgres)

## Using MySQL
Create a database and set:
```bash
export DATABASE_URL="mysql+pymysql://user:password@host:3306/dbname"
pip install pymysql
python app.py
```
(Or on Windows PowerShell: `$env:DATABASE_URL="mysql+pymysql://..."`)

## Security notes
- Change `SECRET_KEY` (env var) in production.
- Create users via the "Create User" link (visible to admin).
