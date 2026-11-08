"""Manual entry point: python -m audio_duckd."""

import argparse
from dataclasses import asdict
import json
import logging
import signal
from threading import Event

from .backend import BackendError, PulseBackend
from .policy import DuckingPolicy
from .config import ConfigError, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Attenuate target applications while Linphone streams exist")
    parser.add_argument("--inspect", action="store_true", help="Print streams as JSON without modifying audio")
    parser.add_argument("--config", metavar="FILE", help="JSON configuration file")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopped = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    backend = None
    policy = None
    try:
        backend = PulseBackend(config)
        if args.inspect:
            print(json.dumps([asdict(s) for s in backend.streams()], indent=2))
            return 0
        policy = DuckingPolicy(backend, config)
        logging.info("audio-duckd started; polling every 0.5 s")
        while not stopped.is_set():
            policy.refresh()
            stopped.wait(0.5)
        return 0
    except (BackendError, ImportError, OSError, RuntimeError) as exc:
        logging.error("Could not run audio-duckd: %s", exc)
        return 1
    finally:
        if policy is not None:
            try:
                policy.refresh(restoring=True)
                if policy.saved:
                    logging.error("Some streams remain unrestored; check target application volumes")
            except BackendError as exc:
                logging.error("Could not restore target volumes on exit: %s", exc)
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
