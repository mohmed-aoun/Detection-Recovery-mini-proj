import requests
import time
import random
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CLIENT")

PRIMARY_URL = "http://127.0.0.1:5000/request"
BACKUP_URL  = "http://127.0.0.1:5001/request"
FAILBACK_RETRY_INTERVAL = 3

MSG_TYPES   = ["READ", "WRITE", "DELETE", "UPDATE", "PING"]
SESSION_MSG = "EMERGENCY CALL"

use_backup        = False
failback_attempts = 0


def make_data(i, mode):
    if mode == "session":
        return {"type": SESSION_MSG, "id": i, "priority": "CRITICAL"}
    return {
        "type": random.choice(MSG_TYPES),
        "payload": f"data-{random.randint(100, 999)}",
        "id": i,
    }


def send_request(data):
    global use_backup, failback_attempts

    # While on backup, periodically try to return to primary
    if use_backup:
        failback_attempts += 1
        if failback_attempts >= FAILBACK_RETRY_INTERVAL:
            failback_attempts = 0
            try:
                res = requests.post(PRIMARY_URL, json=data, timeout=2)
                logger.info(f"Primary recovered, switching back: {res.json()}")
                use_backup = False
                return
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                logger.warning("Primary still down, staying on backup...")

    if not use_backup:
        try:
            res = requests.post(PRIMARY_URL, json=data, timeout=2)
            logger.info(f"Primary response: {res.json()}")
            return
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning("Primary failed, switching to backup...")
            use_backup = True

    try:
        res = requests.post(BACKUP_URL, json=data, timeout=2)
        logger.info(f"Backup response: {res.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Backup also failed: {e}")


def run_simple():
    """10 requests, one per second."""
    logger.info("=== Simple mode: 10 requests ===")
    for i in range(10):
        data = make_data(i, "simple")
        send_request(data)
        time.sleep(1)
    logger.info("Simple mode complete.")


def run_stress():
    """Burst of N requests with 0.1 s delay (default 20)."""
    burst = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    logger.info(f"=== Stress mode: {burst} requests ===")
    for i in range(burst):
        data = make_data(i, "stress")
        send_request(data)
        time.sleep(0.1)
    logger.info("Stress mode complete.")


def run_session():
    """Continuous EMERGENCY CALL requests until Ctrl-C."""
    logger.info("=== Session mode: continuous (Ctrl-C to stop) ===")
    i = 0
    try:
        while True:
            data = make_data(i, "session")
            send_request(data)
            i += 1
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"Session mode stopped after {i} requests.")


MODES = {
    "simple":  run_simple,
    "stress":  run_stress,
    "session": run_session,
}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "simple"
    if mode not in MODES:
        print(f"Usage: python client.py [simple|stress|session] [stress_burst]")
        sys.exit(1)
    MODES[mode]()