import asyncio
import logging
import os
import threading

from werkzeug.serving import make_server

from terabox_gateway.api import app
from bot import run_bot

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class HealthServer(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.server = make_server("0.0.0.0", int(os.getenv("PORT", "5000")), app)

    def run(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()


if __name__ == "__main__":
    server = HealthServer()
    server.start()
    logging.info("Resolver HTTP server started")
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
