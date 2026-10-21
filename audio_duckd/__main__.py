"""Arranque manual: python -m audio_duckd."""

import argparse
from dataclasses import asdict
import json
import logging
import signal
from threading import Event

from .backend import BackendError, PulseBackend
from .policy import DuckingPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Baja Brave al 20 % mientras exista Linphone")
    parser.add_argument("--inspect", action="store_true", help="Imprime streams como JSON sin modificar audio")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopped = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    backend = None
    policy = None
    try:
        backend = PulseBackend()
        if args.inspect:
            print(json.dumps([asdict(s) for s in backend.streams()], indent=2))
            return 0
        policy = DuckingPolicy(backend)
        logging.info("audio-duckd iniciado; sondeo cada 0,5 s")
        while not stopped.is_set():
            policy.refresh()
            stopped.wait(0.5)
        return 0
    except (BackendError, ImportError, OSError, RuntimeError) as exc:
        logging.error("No se pudo ejecutar audio-duckd: %s", exc)
        return 1
    finally:
        if policy is not None:
            try:
                policy.refresh(restoring=True)
                if policy.saved:
                    logging.error("Quedan streams sin restaurar; comprueba el volumen de Brave")
            except BackendError as exc:
                logging.error("No se pudo restaurar Brave al salir: %s", exc)
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
