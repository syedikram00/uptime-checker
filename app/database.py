from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import os
import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/uptime")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class MonitorDB(Base):
    __tablename__ = "monitors"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    webhook_url = Column(String, nullable=True)
    checks = relationship("CheckResultDB", back_populates="monitor")

class CheckResultDB(Base):
    __tablename__ = "check_results"
    id = Column(String, primary_key=True)
    monitor_id = Column(String, ForeignKey("monitors.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_up = Column(Boolean, nullable=False)
    monitor = relationship("MonitorDB", back_populates="checks")

def init_db():
    Base.metadata.create_all(bind=engine)
