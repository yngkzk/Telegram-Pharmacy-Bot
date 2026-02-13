from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    user_name = Column(String)
    user_password = Column(String)
    region = Column(String)

    join_date = Column(DateTime, default=datetime.now)
    logged_in = Column(Integer, default=1)
    is_approved = Column(Boolean, default=False)