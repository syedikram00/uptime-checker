from fastapi import FastAPI, HTTPException, Request, Form
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid
import requests
import datetime

from app.database import SessionLocal, MonitorDB, CheckResultDB, init_db

app = FastAPI()

init_db()  # creates tables on startup if they don't exist


class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl
    webhook_url: str | None = None


class Monitor(MonitorCreate):
    id: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/monitors", response_model=Monitor)
def add_monitor(monitor: MonitorCreate):
    db = SessionLocal()

    monitor_id = str(uuid.uuid4())

    new_monitor = MonitorDB(
        id=monitor_id,
        name=monitor.name,
        url=str(monitor.url),
        webhook_url=monitor.webhook_url,
    )

    db.add(new_monitor)
    db.commit()
    db.close()

    return {
        "id": monitor_id,
        "name": monitor.name,
        "url": str(monitor.url),
        "webhook_url": monitor.webhook_url,
    }


@app.get("/monitors")
def list_monitors():
    db = SessionLocal()
    result = db.query(MonitorDB).all()
    db.close()

    return [
        {
            "id": m.id,
            "name": m.name,
            "url": m.url,
        }
        for m in result
    ]


@app.get("/monitors/{monitor_id}")
def get_monitor(monitor_id: str):
    db = SessionLocal()

    monitor = (
        db.query(MonitorDB)
        .filter(MonitorDB.id == monitor_id)
        .first()
    )

    db.close()

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    return {
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
    }


@app.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: str):
    db = SessionLocal()

    monitor = (
        db.query(MonitorDB)
        .filter(MonitorDB.id == monitor_id)
        .first()
    )

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

    monitor = (
        db.query(MonitorDB)
        .filter(MonitorDB.id == monitor_id)
        .first()
    )

    if not monitor:
        db.close()
        raise HTTPException(status_code=404, detail="Monitor not found")

    checks = (
        db.query(CheckResultDB)
        .filter(CheckResultDB.monitor_id == monitor_id)
        .order_by(CheckResultDB.timestamp.desc())
        .all()
    )

    db.close()

    return [
        {
            "timestamp": c.timestamp.isoformat(),
            "is_up": c.is_up,
        }
        for c in checks
    ]


# -----------------------------
# NEW UPTIME ENDPOINT
# -----------------------------
@app.get("/monitors/{monitor_id}/uptime")
def get_uptime_percentage(monitor_id: str):
    db = SessionLocal()

    monitor = (
        db.query(MonitorDB)
        .filter(MonitorDB.id == monitor_id)
        .first()
    )

    if not monitor:
        db.close()
        raise HTTPException(status_code=404, detail="Monitor not found")

    checks = (
        db.query(CheckResultDB)
        .filter(CheckResultDB.monitor_id == monitor_id)
        .all()
    )

    db.close()

    if not checks:
        return {
            "monitor_id": monitor_id,
            "uptime_percentage": None,
            "total_checks": 0,
        }

    up_count = sum(1 for c in checks if c.is_up)
    total_count = len(checks)
    uptime_percentage = round((up_count / total_count) * 100, 2)

    return {
        "monitor_id": monitor_id,
        "uptime_percentage": uptime_percentage,
        "total_checks": total_count,
        "up_checks": up_count,
        "down_checks": total_count - up_count,
    }
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    all_monitors = db.query(MonitorDB).all()

    monitor_data = []
    for m in all_monitors:
        checks = db.query(CheckResultDB).filter(CheckResultDB.monitor_id == m.id).order_by(CheckResultDB.timestamp.desc()).all()
        total = len(checks)
        up_count = sum(1 for c in checks if c.is_up)
        uptime_pct = round((up_count / total) * 100, 2) if total > 0 else None
        latest_status = checks[0].is_up if checks else None

        monitor_data.append({
            "id": m.id,
            "name": m.name,
            "url": m.url,
            "uptime_pct": uptime_pct,
            "latest_status": latest_status,
            "total_checks": total
        })

    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "monitors": monitor_data})

@app.post("/add-monitor", response_class=HTMLResponse)
def add_monitor_form(request: Request, name: str = Form(...), url: str = Form(...), webhook_url: str = Form(None)):
    db = SessionLocal()
    new_monitor = MonitorDB(
        id=str(uuid.uuid4()),
        name=name,
        url=url,
        webhook_url=webhook_url if webhook_url else None
    )
    db.add(new_monitor)
    db.commit()
    db.close()
    return dashboard(request)


@app.post("/delete-monitor/{monitor_id}", response_class=HTMLResponse)
def delete_monitor_form(request: Request, monitor_id: str):
    db = SessionLocal()
    monitor = db.query(MonitorDB).filter(MonitorDB.id == monitor_id).first()
    if monitor:
        db.query(CheckResultDB).filter(CheckResultDB.monitor_id == monitor_id).delete()
        db.delete(monitor)
        db.commit()
    db.close()
    return dashboard(request)
