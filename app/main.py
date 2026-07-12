from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import uuid

app = FastAPI()

monitors = {}

class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl

class Monitor(MonitorCreate):
    id: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/monitors", response_model=Monitor)
def add_monitor(monitor: MonitorCreate):
    monitor_id = str(uuid.uuid4())
    new_monitor = {"id": monitor_id, "name": monitor.name, "url": str(monitor.url)}
    monitors[monitor_id] = new_monitor
    return new_monitor

@app.get("/monitors")
def list_monitors():
    return list(monitors.values())

@app.get("/monitors/{monitor_id}")
def get_monitor(monitor_id: str):
    if monitor_id not in monitors:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitors[monitor_id]

@app.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: str):
    if monitor_id not in monitors:
        raise HTTPException(status_code=404, detail="Monitor not found")
    del monitors[monitor_id]
    return {"message": "Monitor deleted"}
