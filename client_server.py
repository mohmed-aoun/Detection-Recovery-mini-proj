from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import threading
import logging
import time
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CLIENT")

app = Flask(__name__)
CORS(app, origins="*")

PRIMARY = "http://127.0.0.1:5000/request"
BACKUP  = "http://127.0.0.1:5001/request"
FAILBACK_RETRY_INTERVAL = 3

# Shared state
state = {
    "running": False,
    "mode": None,
    "use_backup": False,
    "failback_attempts": 0,
    "req_count": 0,
    "total": 0,
    "feed": [],
    "stress_burst": 20,
}
lock = threading.Lock()
stop_event = threading.Event()

MSG_TYPES = ["READ", "WRITE", "DELETE", "UPDATE", "PING"]
SESSION_MSG = "EMERGENCY CALL"

def make_data(i, mode):
    if mode == "session":
        return {"type": SESSION_MSG, "id": i, "priority": "CRITICAL"}
    return {
        "type": random.choice(MSG_TYPES),
        "payload": f"data-{random.randint(100,999)}",
        "id": i
    }

def send_request(data):
    with lock:
        use_backup = state["use_backup"]
        failback_attempts = state["failback_attempts"]

    # Periodically try to return to primary
    if use_backup:
        failback_attempts += 1
        if failback_attempts >= FAILBACK_RETRY_INTERVAL:
            failback_attempts = 0
            try:
                res = requests.post(PRIMARY, json=data, timeout=2)
                logger.info(f"Primary recovered, switching back")
                with lock:
                    state["use_backup"] = False
                    state["failback_attempts"] = 0
                add_feed("PRIMARY", data, "OK", recovered=True)
                return
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                logger.warning("Primary still down, staying on backup...")
                with lock:
                    state["failback_attempts"] = failback_attempts

    if not use_backup:
        try:
            res = requests.post(PRIMARY, json=data, timeout=2)
            logger.info(f"Primary response: {res.json()}")
            add_feed("PRIMARY", data, "OK")
            return
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning("Primary failed, switching to backup...")
            with lock:
                state["use_backup"] = True
            add_feed("PRIMARY", data, "TIMEOUT")

    try:
        res = requests.post(BACKUP, json=data, timeout=2)
        logger.info(f"Backup response: {res.json()}")
        add_feed("BACKUP", data, "OK")
    except requests.exceptions.RequestException as e:
        logger.error(f"Backup failed: {e}")
        add_feed("BACKUP", data, "FAIL")

def add_feed(who, data, status, recovered=False):
    entry = {
        "who": who,
        "msg": f"{data.get('type','?')} · id:{data.get('id','?')}",
        "status": status,
        "recovered": recovered,
        "time": time.strftime("%H:%M:%S")
    }
    with lock:
        state["feed"].insert(0, entry)
        if len(state["feed"]) > 50:
            state["feed"].pop()

def run_simple():
    total = 10
    with lock:
        state["total"] = total
    for i in range(total):
        if stop_event.is_set():
            break
        data = make_data(i, "simple")
        with lock:
            state["req_count"] = i + 1
        send_request(data)
        time.sleep(1)
    with lock:
        state["running"] = False
    logger.info("Simple mode complete")

def run_stress():
    with lock:
        burst = state["stress_burst"]
        state["total"] = burst
    for i in range(burst):
        if stop_event.is_set():
            break
        data = make_data(i, "stress")
        with lock:
            state["req_count"] = i + 1
        send_request(data)
        time.sleep(0.1)
    with lock:
        state["running"] = False
    logger.info("Stress mode complete")

def run_session():
    i = 0
    with lock:
        state["total"] = 0
    while not stop_event.is_set():
        data = make_data(i, "session")
        with lock:
            state["req_count"] = i + 1
            state["total"] = i + 1
        send_request(data)
        i += 1
        time.sleep(1)
    with lock:
        state["running"] = False
    logger.info("Session mode stopped")

def monitor_primary():
    global state
    while True:
        time.sleep(2)
        with lock:
            if not state["use_backup"]:
                continue
        try:
            requests.get("http://127.0.0.1:5000/status", timeout=1)
            with lock:
                state["use_backup"] = False
                state["failback_attempts"] = 0
            logger.info("Primary recovered — switching back")
        except:
            pass

@app.route("/start", methods=["POST"])
def start():
    with lock:
        if state["running"]:
            return jsonify({"error": "already running"}), 400
        body = request.json or {}
        mode = body.get("mode", "simple")
        state["mode"] = mode
        state["running"] = True
        state["use_backup"] = False
        state["failback_attempts"] = 0
        state["req_count"] = 0
        state["feed"] = []
        if "stress_burst" in body:
            state["stress_burst"] = int(body["stress_burst"])

    stop_event.clear()
    logger.info(f"Starting {mode} mode")

    target = {"simple": run_simple, "stress": run_stress, "session": run_session}.get(mode, run_simple)
    threading.Thread(target=target, daemon=True).start()
    return jsonify({"status": "started", "mode": mode})

@app.route("/stop", methods=["POST"])
def stop():
    stop_event.set()
    with lock:
        state["running"] = False
    logger.info("Client stopped")
    return jsonify({"status": "stopped"})

@app.route("/status", methods=["GET"])
def status():
    with lock:
        return jsonify({
            "running": state["running"],
            "mode": state["mode"],
            "use_backup": state["use_backup"],
            "req_count": state["req_count"],
            "total": state["total"],
            "feed": state["feed"][:20],
            "stress_burst": state["stress_burst"],
        })

@app.route("/restart-primary", methods=["POST"])
def restart_primary():
    import subprocess, sys, os
    project_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen(
        [sys.executable, os.path.join(project_dir, "primary_server.py")],
        cwd=project_dir
    )
    return jsonify({"status": "restarting"})


if __name__ == "__main__":
    threading.Thread(target=monitor_primary, daemon=True).start()
    app.run(port=5002)