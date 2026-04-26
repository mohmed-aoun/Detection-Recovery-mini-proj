from flask import Flask, request, jsonify
import requests
import time
import threading
import logging
import signal
import sys
from flask_cors import CORS
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PRIMARY")

app = Flask(__name__)
CORS(app, origins="*")

data_store = []
backup_down = False
lock = threading.Lock()
stop_event = threading.Event()
start_time = time.time()

def shutdown(signum, frame):
    logger.info("Shutting down — saving data_store...")
    logger.info(f"Total requests processed: {len(data_store)}")
    logger.info("Primary server stopped cleanly.")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

@app.route("/request", methods=["POST"])
def handle_request():
    data = request.json
    data_store.append(data)
    logger.info(f"Received: {data}")
    try:
        requests.post("http://127.0.0.1:5001/replicate", json=data, timeout=1)
    except requests.exceptions.RequestException as e:
        logger.warning(f"Backup not reachable: {e}")
    return jsonify({
        "status": "processed",
        "data": data
    })

@app.route("/status", methods=["GET"])
def status():
    with lock:
        is_backup_down = backup_down
    return jsonify({
        "server": "primary",
        "status": "online",
        "backup_reachable": not is_backup_down,
        "requests_processed": len(data_store),
        "uptime_seconds": round(time.time() - start_time)
    })

def send_heartbeat():
    global backup_down
    while not stop_event.is_set():
        try:
            requests.post("http://127.0.0.1:5001/heartbeat", timeout=1)
            with lock:
                if backup_down:
                    logger.info("Backup server recovered")
                    backup_down = False
                else:
                    logger.debug("Heartbeat sent")
        except requests.exceptions.RequestException:
            with lock:
                if not backup_down:
                    logger.error("Backup not reachable")
                    backup_down = True
        time.sleep(1)

@app.route("/shutdown", methods=["POST"])
def shutdown_server():
    logger.info("Shutdown requested via dashboard")
    threading.Thread(target=lambda: (time.sleep(0.5), os.kill(os.getpid(), signal.SIGTERM))).start()
    return jsonify({"status": "shutting down"})

if __name__ == "__main__":
    threading.Thread(target=send_heartbeat, daemon=True).start()
    app.run(port=5000)