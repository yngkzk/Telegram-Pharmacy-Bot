from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from .base import Base

class MainReport(Base):
    __tablename__ = "main_reports"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.now)
    user = Column(String)
    district = Column(String)
    road = Column(String)
    lpu = Column(String)
    doc_name = Column(String)