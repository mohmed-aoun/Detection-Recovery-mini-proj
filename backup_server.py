from flask import Flask, request, jsonify
import time
import threading
import logging
import signal
import sys
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BACKUP")

app = Flask(__name__)
CORS(app, origins="*")

lock = threading.Lock()
last_heartbeat = time.time()
primary_down = False
replicated_data = []
stop_event = threading.Event()
start_time = time.time()
requests_handled = 0

def shutdown(signum, frame):
    logger.info("Shutting down — saving replicated_data...")
    logger.info(f"Total records replicated: {len(replicated_data)}")
    logger.info("Backup server stopped cleanly.")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    with lock:
        global last_heartbeat
        last_heartbeat = time.time()
    logger.debug("Heartbeat received")
    return jsonify({"status": "alive"})

@app.route("/replicate", methods=["POST"])
def replicate():
    data = request.json
    replicated_data.append(data)
    logger.info(f"Replicated: {data}")
    return jsonify({"status": "replicated"})

@app.route("/request", methods=["POST"])
def handle_request():
    global requests_handled
    data = request.json
    with lock:
        requests_handled += 1
    logger.info(f"ACTIVE — Handling request: {data}")
    return jsonify({
        "status": "processed by backup",
        "data": data
    })

@app.route("/status", methods=["GET"])
def status():
    with lock:
        is_primary_down = primary_down
        elapsed = round(time.time() - last_heartbeat, 1)
        handled = requests_handled
    return jsonify({
        "server": "backup",
        "status": "online",
        "mode": "ACTIVE" if is_primary_down else "STANDBY",
        "primary_alive": not is_primary_down,
        "last_heartbeat_seconds_ago": elapsed,
        "records_replicated": len(replicated_data),
        "requests_handled": handled,
        "uptime_seconds": round(time.time() - start_time)
    })

def monitor_heartbeat():
    global primary_down
    while not stop_event.is_set():
        time.sleep(1)
        with lock:
            elapsed = time.time() - last_heartbeat
            is_down = primary_down
        if elapsed > 3:
            if not is_down:
                logger.error("Primary server is DOWN (heartbeat lost)")
                with lock:
                    primary_down = True
        else:
            if is_down:
                logger.info("Primary server recovered")
                with lock:
                    primary_down = False

if __name__ == "__main__":
    threading.Thread(target=monitor_heartbeat, daemon=True).start()
    app.run(port=5001)