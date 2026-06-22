# SplitSmart

SplitSmart uses MySQL 8 through SQLAlchemy and PyMySQL.

## MySQL configuration

Create a `.env` file in the project folder:

```env
SECRET_KEY=replace-with-a-random-secret
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=splitsmart
```

The database name can be changed through `DB_NAME`.

## Create the database and tables

With the virtual environment activated:

```powershell
python setup_mysql.py
```

This creates the configured database when necessary and creates these tables:

- `users`
- `groups`
- `group_members`
- `expenses`
- `expense_shares`
- `settlements`

## Run the application

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

You can inspect the database in MySQL Workbench using the same host, port, user,
and password from `.env`.
