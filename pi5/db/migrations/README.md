# Database Migrations (Alembic)

This folder is a placeholder for Alembic migration scaffolding.

## Bootstrapping

From the repo root:

```bash
pip install alembic
alembic init pi5/db/migrations   # only if you want the full generated layout
```

`env.py` here is pre-wired to the project's ORM metadata
(`pi5.db.models.Base`) and reads `DATABASE_URL` from `pi5.config`.

## Minimal `alembic.ini`

Create an `alembic.ini` at the repo root with at least:

```ini
[alembic]
script_location = pi5/db/migrations
# sqlalchemy.url is set programmatically from config.DATABASE_URL in env.py

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

## Common commands

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
alembic downgrade -1
```

For quick local bring-up without Alembic, use `pi5.db.connection.init_db()`.

Generated migration scripts belong in a `versions/` subdirectory here.
