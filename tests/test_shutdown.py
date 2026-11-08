"""Exercise the real polling policy with a simulated backend and signal delivery."""

from dataclasses import replace
import signal
from threading import Event
from unittest.mock import patch

import pytest

from audio_duckd.__main__ import main
from audio_duckd.backend import BackendError, Stream


class ShutdownBackend:
    def __init__(self):
        self.target = Stream(1, "playback", "brave", 101, "42", (0.1, 0.05), mute=True)
        self.items = [self.target, Stream(2, "capture", "linphone", 102, "43", (1.0,))]
        self.writes = []
        self.closed = False
        self.enumerations = 0
        self.fail_enumerations = set()
        self.fail_restore = False
        self.fail_close = False

    def streams(self):
        self.enumerations += 1
        if self.enumerations in self.fail_enumerations:
            raise BackendError("enumeration unavailable")
        return list(self.items)

    def set_volume(self, stream, volumes):
        assert not self.closed
        if self.fail_restore and volumes == self.target.volumes:
            raise BackendError("restore write unavailable")
        self.writes.append((stream.identity, volumes))
        self.items = [replace(s, volumes=volumes) if s.identity == stream.identity else s
                      for s in self.items]

    def close(self):
        self.closed = True
        if self.fail_close:
            raise BackendError("close unavailable")


@pytest.fixture
def run_daemon():
    def run(backend, *, signum=signal.SIGTERM, on_wait=None, inspect=False, deliver_signal=True):
        handlers = {}
        previous = {sig: object() for sig in (signal.SIGINT, signal.SIGTERM)}
        stopped = Event()

        def install(sig, handler):
            old = handlers.get(sig, previous[sig])
            handlers[sig] = handler
            return old

        def wait(timeout):
            assert timeout == 0.5
            if on_wait is not None:
                on_wait()
            if not deliver_signal:
                return False
            handlers[signum](signum, None)
            # Repeated termination requests must not interrupt restoration.
            handlers[signum](signum, None)
            assert stopped.is_set()

        with patch("sys.argv", ["audio-duckd", *(["--inspect"] if inspect else [])]), \
             patch("audio_duckd.__main__.PulseBackend", return_value=backend), \
             patch("audio_duckd.__main__.signal.signal", side_effect=install), \
             patch("audio_duckd.__main__.Event", return_value=stopped), \
             patch.object(stopped, "wait", side_effect=wait):
            result = main()
        assert handlers == previous
        return result
    return run


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_during_ducking_restores_channels_and_closes(run_daemon, signum):
    backend = ShutdownBackend()
    assert run_daemon(backend, signum=signum) == 0
    assert backend.writes == [(backend.target.identity, (0.1 * 0.2, 0.05 * 0.2)),
                              (backend.target.identity, backend.target.volumes)]
    assert backend.items[0].mute
    assert backend.closed


@pytest.mark.parametrize("recover", [False, True])
def test_polling_failure_attempts_restore_then_closes(run_daemon, recover, caplog):
    backend = ShutdownBackend()
    backend.fail_enumerations = {2} if recover else {2, 3}
    assert run_daemon(backend, deliver_signal=False) == 1
    assert backend.closed
    assert (backend.items[0].volumes == backend.target.volumes) == recover
    assert "Could not run audio-duckd" in caplog.text
    if not recover:
        assert "Unrestored target identities=" in caplog.text
        assert "enumeration unavailable" in caplog.text


def test_restore_write_failure_is_reported_and_backend_closes(run_daemon, caplog):
    backend = ShutdownBackend()
    backend.fail_restore = True
    assert run_daemon(backend) == 1
    assert backend.closed
    assert "Could not restore target identity=" in caplog.text
    assert str(backend.target.identity) in caplog.text
    assert "restore write unavailable" in caplog.text
    assert "Unrestored target identities=" in caplog.text


def test_close_failure_is_reported(run_daemon, caplog):
    backend = ShutdownBackend()
    backend.fail_close = True
    assert run_daemon(backend) == 1
    assert backend.items[0].volumes == backend.target.volumes
    assert "Could not close audio backend" in caplog.text


def test_inspection_only_enumerates_and_closes(run_daemon, capsys):
    backend = ShutdownBackend()
    assert run_daemon(backend, inspect=True) == 0
    assert backend.writes == []
    assert backend.closed
    assert '"binary": "brave"' in capsys.readouterr().out


@pytest.mark.parametrize("inspect", [False, True])
def test_initial_enumeration_failure_is_not_an_empty_list(run_daemon, inspect, caplog):
    backend = ShutdownBackend()
    backend.fail_enumerations = {1}
    assert run_daemon(backend, inspect=inspect) == 1
    assert backend.closed
    assert backend.writes == []
    assert "enumeration unavailable" in caplog.text


def test_channel_change_at_shutdown_reports_unrestored_target(run_daemon, caplog):
    backend = ShutdownBackend()

    def change_channels():
        backend.items[0] = replace(backend.items[0], volumes=(0.02,))

    assert run_daemon(backend, on_wait=change_channels) == 1
    assert backend.closed
    assert len(backend.writes) == 1
    assert "channel count changed (saved=2, current=1)" in caplog.text
    assert str(backend.target.identity) in caplog.text
