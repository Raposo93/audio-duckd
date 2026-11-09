"""Manual entry point: python -m audio_duckd."""

import argparse
from dataclasses import asdict
import json
import logging
import signal
from threading import Event

from .backend import BackendDisconnected, BackendError, PulseBackend
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
    previous_handlers = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
    backend = None
    policy = None
    result = 0
    writes_suspended = False
    try:
        if args.inspect:
            backend = PulseBackend(config)
            print(json.dumps([asdict(s) for s in backend.streams()], indent=2))
        else:
            logging.info("audio-duckd started; polling every 0.5 s")
            retry_delay = 0.5
            while not stopped.is_set():
                try:
                    if backend is None:
                        backend = PulseBackend(config)
                        policy = DuckingPolicy(backend, config, writes_suspended=writes_suspended)
                        logging.info("Audio server connected; starting a new stream session")
                    if stopped.is_set():
                        break
                    policy.refresh()
                except BackendDisconnected as exc:
                    if policy is not None and policy.saved:
                        writes_suspended = True
                        result = 1
                        logging.error(
                            "Volume writes suspended after disconnect; unrestored target "
                            "identities=%s; check target application volumes and restart the daemon",
                            list(policy.saved),
                        )
                    policy = None
                    if backend is not None:
                        try:
                            backend.close()
                        except (BackendError, OSError, RuntimeError) as close_exc:
                            logging.error("Could not close disconnected audio backend: %s", close_exc)
                            result = 1
                        backend = None
                    logging.warning("Audio server unavailable: %s; retrying in %s s", exc, retry_delay)
                    stopped.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, 5.0)
                    continue
                retry_delay = 0.5
                stopped.wait(0.5)
    except (BackendError, ImportError, OSError, RuntimeError) as exc:
        logging.error("Could not run audio-duckd: %s", exc)
        result = 1
    finally:
        try:
            if policy is not None:
                try:
                    policy.refresh(restoring=True)
                except (BackendError, OSError, RuntimeError) as exc:
                    logging.error("Could not restore target volumes on exit: %s", exc)
                    result = 1
                if policy.saved:
                    logging.error(
                        "Unrestored target identities=%s; check target application volumes",
                        list(policy.saved),
                    )
                    result = 1
        finally:
            try:
                if backend is not None:
                    try:
                        backend.close()
                    except (BackendError, OSError, RuntimeError) as exc:
                        logging.error("Could not close audio backend on exit: %s", exc)
                        result = 1
            finally:
                for signum, handler in previous_handlers.items():
                    signal.signal(signum, handler)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
