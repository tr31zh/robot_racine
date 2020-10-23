#!/usr/bin/env python3
"""
Very simple HTTP server in python for logging requests
Usage::
    ./server.py [<port>]
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import time
import os
import sys
import psutil
from datetime import datetime as dt
import json


class MemoryFilter(logging.Filter):

    last_process_mem = 0

    def filter(self, record):
        process: psutil.Process = psutil.Process(os.getpid())
        pmp = process.memory_percent()
        sign = (
            "+" if pmp > self.last_process_mem else "-" if pmp < self.last_process_mem else "="
        )
        record.mem_data = f"µ{sign} {pmp:02.2f}%"
        self.last_process_mem = pmp
        return True


log_file_handler = logging.FileHandler(
    os.path.join("logs", f"{dt.now().strftime('%Y%m%d %H%M%S')}.log"),
    mode="a",
    delay=True,
)
log_file_handler.addFilter(MemoryFilter())

log_stdout_handler = logging.StreamHandler(sys.stdout)
log_stdout_handler.addFilter(MemoryFilter())


if not os.path.exists("logs"):
    os.mkdir("logs")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(mem_data)s - %(name)s - %(levelname)s] - %(message)s",
    handlers=[
        log_stdout_handler,
        log_file_handler,
    ],
)

logger = logging.getLogger("test_server")


class S(BaseHTTPRequestHandler):
    force_stop = False

    def _set_response(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        logger.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        self._set_response()
        self.wfile.write("GET request for {}".format(self.path).encode("utf-8"))

    def send_success(self, data):
        self._set_response()
        logger.info(f"Sending response for {data}")
        self.wfile.write(data["action"].encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])  # <--- Gets the size of data
        post_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
        logger.info(f"Received: {post_data}")

        if post_data["action"] == "stop":
            self.force_stop = True
            self.send_success(post_data)
        else:
            for _ in range(20):
                time.sleep(0.1)
                if self.force_stop:
                    self.force_stop = False
                    break
            else:
                self.send_success(post_data)


def run(server_class=HTTPServer, handler_class=S, port=8000):
    logger.info("Starting test server")

    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logger.info("Starting httpd...\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logger.info("Stopping httpd...\n")


if __name__ == "__main__":
    from sys import argv

    if len(argv) == 2:
        run(port=int(argv[1]))
    else:
        run()