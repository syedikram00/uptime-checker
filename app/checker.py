from app.database import SessionLocal, MonitorDB, CheckResultDB
import requests
import uuid
import datetime

def send_alert(webhook_url: str, monitor_name: str, is_up: bool):
    if not webhook_url:
        return
    status_text = "back UP" if is_up else "DOWN"
    payload = {"content": f"Alert: {monitor_name} is {status_text}"}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"Failed to send webhook: {e}")

def check_all_monitors():
    db = SessionLocal()
    try:
        monitors = db.query(MonitorDB).all()
        for monitor in monitors:
            try:
                response = requests.get(monitor.url, timeout=10)
                is_up = response.status_code < 400
            except requests.RequestException:
                is_up = False

            last_check = db.query(CheckResultDB)\
                .filter(CheckResultDB.monitor_id == monitor.id)\
                .order_by(CheckResultDB.timestamp.desc())\
                .first()

            state_changed = last_check is not None and last_check.is_up != is_up

            result = CheckResultDB(
                id=str(uuid.uuid4()),
                monitor_id=monitor.id,
                timestamp=datetime.datetime.utcnow(),
                is_up=is_up
            )
            db.add(result)

            if state_changed and monitor.webhook_url:
                send_alert(monitor.webhook_url, monitor.name, is_up)

        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    check_all_monitors()
