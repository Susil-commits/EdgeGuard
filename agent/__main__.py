"""Agent main loop."""

import logging
import os
import time

from agent.collector import collect_metrics
from agent.sender import replay_spool, send_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

COLLECT_INTERVAL_S = int(os.environ.get("COLLECT_INTERVAL_S", "30"))


def main() -> None:
    logger.info("EdgeGuard agent starting. Interval: %ds", COLLECT_INTERVAL_S)

    # Replay any events buffered during a prior outage
    replay_spool()

    while True:
        try:
            metrics = collect_metrics()
            send_metrics(metrics)
        except Exception as e:
            logger.error("Unexpected error in collect/send cycle: %s", e)
        time.sleep(COLLECT_INTERVAL_S)


if __name__ == "__main__":
    main()
