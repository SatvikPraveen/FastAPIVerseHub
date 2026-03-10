# File: app/models/base.py
"""Single shared declarative base for all SQLAlchemy models.

All models MUST import Base from here so that Base.metadata is
complete and Alembic can detect every table in one pass.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
