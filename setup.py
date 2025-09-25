from setuptools import find_packages, setup

package_files = [
    "alembic.ini",
    "alembic/env.py",
    "alembic/env_async.py",
    "alembic/script.py.mako",
    "alembic/versions/*.py",
    "alembic/versions/*.sql",
    "migrations/*.py",
    "migrations/*.sql",
    "migrations/scripts/*.sql",
]

setup(
    name="rcm-schema",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"rcm_schema": package_files},
    python_requires=">=3.11",
    install_requires=[
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "asyncpg>=0.29.0",  # Required for async database operations
        "pgvector>=0.2.4",  # Vector column support used in models
        "psycopg2-binary>=2.9.9",  # Sync connection support for validators/scripts
    ],
    description="RCM Schema - Shared database models for RCM services",
    author="RCM Team",
)
