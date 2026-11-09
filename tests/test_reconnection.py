"""Simulate server sessions without connecting to an audio server."""

from dataclasses import replace
import signal
from threading import Event
from unittest.mock import Mock, patch

import pytest

from audio_duckd.__main__ import main
from audio_duckd.backend import BackendDisconnected, Stream


class SessionBackend:
    def __init__(self, *items):
        self.items = list(items)
        self.writes = []
        self.closed = False
        self.disconnect = False

    def streams(self):
        assert not self.closed
        if self.disconnect:
            raise BackendDisconnected("simulated server loss")
        return list(self.items)

    def set_volume(self, target, volumes):
        assert not self.closed
        if self.disconnect:
            raise BackendDisconnected("simulated write loss")
        self.writes.append((target.identity, volumes))
        self.items = [replace(s, volumes=volumes) if s.identity == target.identity else s
                      for s in self.items]

    def close(self):
        self.closed = True


def run_sessions(attempts, on_wait):
    stopped = Event()
    factory = Mock(side_effect=attempts)
    waits = []

    def wait(seconds):
        waits.append(seconds)
        on_wait(stopped, waits)
        return stopped.is_set()

    with patch("sys.argv", ["audio-duckd"]), \
         patch("audio_duckd.__main__.PulseBackend", factory), \
         patch("audio_duckd.__main__.signal.signal"), \
         patch("audio_duckd.__main__.Event", return_value=stopped), \
         patch.object(stopped, "wait", side_effect=wait):
        result = main()
    return result, factory.call_count, waits


def test_startup_retries_have_capped_backoff_and_stop_without_another_attempt():
    attempts = [BackendDisconnected("server unavailable") for _ in range(7)]

    def stop(event, waits):
        if len(waits) == 7:
            event.set()

    result, count, waits = run_sessions(attempts, stop)
    assert result == 0
    assert count == 7
    assert waits == [0.5, 1.0, 2.0, 4.0, 5.0, 5.0, 5.0]


def test_reconnection_enumerates_fresh_streams_and_recalculates_linphone_activity():
    target = Stream(1, "playback", "brave", 101, "42", (0.8, 0.6))
    phone = Stream(2, "capture", "linphone", 102, "43", (1.0,))
    first = SessionBackend(target)
    # All identity fields may be reused by the new server session.
    replacement = replace(target, volumes=(0.3, 0.2))
    second = SessionBackend(replacement, phone)

    def advance(event, waits):
        if len(waits) == 1:
            first.disconnect = True
        elif len(waits) == 3:
            event.set()

    result, count, waits = run_sessions([first, second], advance)
    assert result == 0
    assert count == 2
    assert first.closed and second.closed
    assert first.writes == []
    assert second.writes == [(replacement.identity, (0.3 * 0.2, 0.2 * 0.2)),
                             (replacement.identity, replacement.volumes)]
    assert waits == [0.5, 0.5, 0.5]


def test_successful_poll_resets_retry_delay():
    first = SessionBackend()
    second = SessionBackend()

    def advance(event, waits):
        if len(waits) == 3:
            first.disconnect = True
        elif len(waits) == 5:
            event.set()

    result, count, waits = run_sessions([
        BackendDisconnected("offline"), BackendDisconnected("offline"), first, second,
    ], advance)
    assert result == 0
    assert count == 4
    assert waits == [0.5, 1.0, 0.5, 0.5, 0.5]
    assert first.closed and second.closed


def test_disconnect_during_ducking_suspends_all_writes_across_later_sessions(caplog):
    target = Stream(1, "playback", "brave", 101, "42", (0.8, 0.6))
    phone = Stream(2, "capture", "linphone", 102, "43", (1.0,))
    first = SessionBackend(target, phone)
    # The new server may reuse every identity field AND retain the ducked volume.
    retained = replace(target, volumes=(0.8 * 0.2, 0.6 * 0.2))
    second = SessionBackend(retained, phone)
    third = SessionBackend(replace(target, index=9, volumes=(0.4, 0.2)), phone)

    def advance(event, waits):
        if len(waits) == 1:
            first.disconnect = True
        elif len(waits) == 3:
            # Ending the call must not release the suspension.
            second.items = [retained]
        elif len(waits) == 4:
            second.disconnect = True
        elif len(waits) == 6:
            event.set()

    result, count, waits = run_sessions([first, second, third], advance)
    assert result == 1
    assert count == 3
    assert first.writes == [(target.identity, (0.8 * 0.2, 0.6 * 0.2))]
    assert second.writes == third.writes == []
    assert first.closed and second.closed and third.closed
    assert "Volume writes suspended after disconnect" in caplog.text
    assert str(target.identity) in caplog.text
    assert "check target application volumes and restart the daemon" in caplog.text
    # After a manual volume check, a fresh invocation can control volumes again.
    corrected = SessionBackend(replace(target, volumes=(0.7, 0.5)), phone)
    result, count, waits = run_sessions([corrected], lambda event, waits: event.set())
    assert result == 0
    assert corrected.writes == [(target.identity, (0.7 * 0.2, 0.5 * 0.2)),
                                (target.identity, (0.7, 0.5))]


def test_write_applied_before_disconnect_still_suspends_reconnected_session(caplog):
    target = Stream(1, "playback", "brave", 101, "42", (0.8, 0.6))
    phone = Stream(2, "capture", "linphone", 102, "43", (1.0,))
    first = SessionBackend(target, phone)
    write = first.set_volume

    def lose_acknowledgement(stream, volumes):
        write(stream, volumes)
        first.disconnect = True
        raise BackendDisconnected("write acknowledgement lost")

    first.set_volume = lose_acknowledgement
    second = SessionBackend(replace(target, volumes=(0.16, 0.12)), phone)

    def stop(event, waits):
        if len(waits) == 2:
            event.set()

    result, count, waits = run_sessions([first, second], stop)
    assert result == 1
    assert count == 2
    assert second.writes == []
    assert first.closed and second.closed
    assert "Volume writes suspended after disconnect" in caplog.text


def test_disconnect_during_restoration_suspends_reconnected_session():
    target = Stream(1, "playback", "brave", 101, "42", (0.8, 0.6))
    phone = Stream(2, "capture", "linphone", 102, "43", (1.0,))
    first = SessionBackend(target, phone)
    write = first.set_volume

    def lose_restore(stream, volumes):
        if volumes == target.volumes:
            first.disconnect = True
            raise BackendDisconnected("restore connection lost")
        write(stream, volumes)

    first.set_volume = lose_restore
    second = SessionBackend(replace(target, volumes=(0.16, 0.12)))

    def advance(event, waits):
        if len(waits) == 1:
            first.items = first.items[:1]
        elif len(waits) == 3:
            event.set()

    result, count, waits = run_sessions([first, second], advance)
    assert result == 1
    assert count == 2
    assert second.writes == []
    assert first.closed and second.closed


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_during_retry_wait_prevents_another_connection_attempt(signum):
    handlers = {}
    stopped = Event()

    def install(sig, handler):
        handlers[sig] = handler

    def wait(timeout):
        assert timeout == 0.5
        handlers[signum](signum, None)
        assert stopped.is_set()

    with patch("sys.argv", ["audio-duckd"]), \
         patch("audio_duckd.__main__.PulseBackend", side_effect=BackendDisconnected("offline")) as factory, \
         patch("audio_duckd.__main__.signal.signal", side_effect=install), \
         patch("audio_duckd.__main__.Event", return_value=stopped), \
         patch.object(stopped, "wait", side_effect=wait):
        assert main() == 0
    factory.assert_called_once()


def test_inspection_does_not_retry_connection_failures(capsys):
    with patch("sys.argv", ["audio-duckd", "--inspect"]), \
         patch("audio_duckd.__main__.PulseBackend", side_effect=BackendDisconnected("offline")) as factory, \
         patch("audio_duckd.__main__.signal.signal"), \
         patch("audio_duckd.__main__.Event.wait") as wait:
        assert main() == 1
    factory.assert_called_once()
    wait.assert_not_called()
    assert capsys.readouterr().out == ""


def test_stop_requested_during_connection_does_not_attenuate():
    stopped = Event()
    target = Stream(1, "playback", "brave", 101, "42", (0.8, 0.6))
    phone = Stream(2, "capture", "linphone", 102, "43", (1.0,))
    backend = SessionBackend(target, phone)

    def connect(config):
        stopped.set()
        return backend

    with patch("sys.argv", ["audio-duckd"]), \
         patch("audio_duckd.__main__.PulseBackend", side_effect=connect), \
         patch("audio_duckd.__main__.signal.signal"), \
         patch("audio_duckd.__main__.Event", return_value=stopped):
        assert main() == 0
    assert backend.closed
    assert backend.writes == []
