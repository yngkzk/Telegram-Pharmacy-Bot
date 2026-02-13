from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class District(Base):
    __tablename__ = "districts"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    region = Column(String, default="АЛА")


class Road(Base):
    __tablename__ = "roads"
    road_id = Column(Integer, primary_key=True)
    district_name = Column(String)
    road_num = Column(Integer)


class LPU(Base):
    __tablename__ = "lpu"
    lpu_id = Column(Integer, primary_key=True)
    road_id = Column(Integer, ForeignKey("roads.road_id"))
    pharmacy_name = Column(String)
    pharmacy_url = Column(String)

    road = relationship("Road")


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
    lpu_id = Column(Integer, ForeignKey("lpu.lpu_id"))
    doctor = Column(String)
    spec_id = Column(Integer)
    numb = Column(Integer)
    birthdate = Column(String)

    lpu = relationship("LPU")


class Medication(Base):
    __tablename__ = "medication"

    id = Column(Integer, primary_key=True)
    prep = Column(String)