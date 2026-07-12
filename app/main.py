from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import uuid
import requests
import datetime

from app.database import SessionLocal, MonitorDB, CheckResultDB, init_db

app = FastAPI()

init_db()  # creates tables on startup if they don't exist

class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl

class Monitor(MonitorCreate):
    id: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_all_monitors():
    db: Session = SessionLocal()
    try:
        all_monitors = db.query(MonitorDB).all()
        for monitor in all_monitors:
            try:
                response = requests.get(monitor.url, timeout=5)
                is_up = response.status_code < 400
            except requests.RequestException:
                is_up = False

            result = CheckResultDB(
                id=str(uuid.uuid4()),
                monitor_id=monitor.id,
                timestamp=datetime.datetime.utcnow(),
                is_up=is_up
            )
            db.add(result)
        db.commit()
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_all_monitors, "interval", seconds=30)
scheduler.start()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/monitors", response_model=Monitor)
def add_monitor(monitor: MonitorCreate):
    db = SessionLocal()
    monitor_id = str(uuid.uuid4())
    new_monitor = MonitorDB(id=monitor_id, name=monitor.name, url=str(monitor.url))
    db.add(new_monitor)
    db.commit()
    db.close()
    return {"id": monitor_id, "name": monitor.name, "url": str(monitor.url)}

@app.get("/monitors")
def list_monitors():
    db = SessionLocal()
    result = db.query(MonitorDB).all()
    db.close()
    return [{"id": m.id, "name": m.name, "url": m.url} for m in result]

@app.get("/monitors/{monitor_id}")
def get_monitor(monitor_id: str):
    db = SessionLocal()
    monitor = db.query(MonitorDB).filter(MonitorDB.id == monitor_id).first()
    db.close()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"id": monitor.id, "name": monitor.name, "url": monitor.url}

@app.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: str):
    db = SessionLocal()
    monitor = db.query(MonitorDB).filter(MonitorDB.id == monitor_id).first()
    if not monitor:
        db.close()
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(monitor)
    db.commit()
    db.close()
    return {"message": "Monitor deleted"}

@app.get("/monitors/{monitor_id}/checks")
def get_check_history(monitor_id: str):
    db = SessionLocal()
    monitor = db.query(MonitorDB).filter(MonitorDB.id == monitor_id).first()
    if not monitor:
        db.close()
        raise HTTPException(status_code=404, detail="Monitor not found")
    checks = db.query(CheckResultDB).filter(CheckResultDB.monitor_id == monitor_id).order_by(CheckResultDB.timestamp.desc()).all()
    db.close()
    return [{"timestamp": c.timestamp.isoformat(), "is_up": c.is_up} for c in checks]
