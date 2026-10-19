import subprocess
import sys
from config import SERVICES
from logger import logger

class ServiceManager():
    def __init__(self):
        self.processes={}

    def start_services(self):
        for name, info in SERVICES.items():
            try:
                logger.info(f"{name} starting")
                process = subprocess.Popen(info["cmd"])
                self.processes[name] = process
                logger.info(f"{name} started")
            except Exception as e:
                logger.critical(f"{name}: {e}")

    def stop_services(self):
        for name, process in self.processes.items():
            logger.info(f"{name} stopping")
            process.terminate()
            logger.info(f"{name} stopped")