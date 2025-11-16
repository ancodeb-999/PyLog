import psutil
import logging
import time
import signal
import sys
from datetime import datetime
from typing import Dict


class ProcessMonitor:
    """Monitor system PIDs and log process creation and termination.

    Behavior:
    - On start, seeds the current PID set but does NOT log existing processes.
    - Periodically polls for PID changes and logs only creations and terminations.
    - Supports Ctrl+C (KeyboardInterrupt) to stop gracefully.

    """

    def __init__(self, interval: float = 1.0, log_file: str = "process_log.txt"):
        self.interval = float(interval)
        self.log_file = log_file
        self.running = False
        # pid -> name mapping to keep human-friendly info for ended processes
        self.pid_info: Dict[int, str] = {}

        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Seed current pids (do not log them as "started")
        try:
            for pid in psutil.pids():
                try:
                    proc = psutil.Process(pid)
                    self.pid_info[pid] = proc.name()
                except psutil.NoSuchProcess:
                    # process gone between listing and inspection
                    continue
        except Exception:
            # If psutil fails for any reason, start with empty state
            self.pid_info = {}

    def _log_start(self, pid: int):
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            created = datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S')
            msg = f"Process Started - PID: {pid}, Name: {name}, Created: {created}"
            logging.info(msg)
            print(msg)
            # store name for later termination logging
            self.pid_info[pid] = name
        except psutil.NoSuchProcess:
            # process disappeared too quickly; ignore
            pass
        except Exception as e:
            logging.error(f"Error logging start for PID {pid}: {e}")

    def _log_end(self, pid: int):
        name = self.pid_info.get(pid)
        if name:
            msg = f"Process Ended - PID: {pid}, Name: {name}"
        else:
            msg = f"Process Ended - PID: {pid}"
        logging.info(msg)
        print(msg)
        # remove from cache if present
        self.pid_info.pop(pid, None)

    def _poll_once(self):
        try:
            current = set(psutil.pids())
        except Exception as e:
            logging.error(f"Failed to list PIDs: {e}")
            current = set()

        previous = set(self.pid_info.keys())

        # newly created
        created = current - previous
        for pid in created:
            self._log_start(pid)

        # ended
        ended = previous - current
        for pid in ended:
            self._log_end(pid)

    def start(self):
        """Start monitoring until Ctrl+C."""
        self.running = True

        # Ensure KeyboardInterrupt works; also set SIGINT handler for completeness
        try:
            signal.signal(signal.SIGINT, lambda s, f: (_ for _ in ()).throw(KeyboardInterrupt()))
        except Exception:
            # signal may not be available in all environments; KeyboardInterrupt will still work
            pass
        logging.info("ProcessMonitor started")
        print("ProcessMonitor started. Press Ctrl+C to stop.")
        try:
            while self.running:
                self._poll_once()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            # graceful shutdown
            logging.info("ProcessMonitor stopping due to KeyboardInterrupt")
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            print("Stopping ProcessMonitor...")
            logging.info("ProcessMonitor stopped by user")


if __name__ == '__main__':
    monitor = ProcessMonitor(interval=1.0)
    try:
        monitor.start()
    except Exception as e:
        logging.error(f"Unhandled error in monitor: {e}")
        print(f"Unhandled error: {e}")
        sys.exit(1)