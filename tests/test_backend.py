from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pytest

from audio_duckd.backend import BackendDisconnected, BackendError, PulseBackend
from audio_duckd.config import Applications, Config


def info(binary="brave", index=1):
    return SimpleNamespace(
        index=index, client=23, mute=True, corked=True,
        proplist={"application.process.binary": binary, "application.process.id": "42"},
        volume=SimpleNamespace(values=[0.7, 0.5]),
    )


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = PulseBackend.__new__(PulseBackend)
        self.backend.config = Config()
        self.backend.api = SimpleNamespace(PulseError=RuntimeError, PulseVolumeInfo=list)
        self.backend.pulse = Mock()
        self.backend.pulse.connected = True
        self.backend.pulse.sink_input_list.return_value = [info()]
        self.backend.pulse.source_output_list.return_value = [info("linphone (deleted)", 2)]

    def test_structured_streams_include_capture_and_normalize_deleted_binary(self):
        playback, capture = self.backend.streams()
        self.assertEqual(playback.volumes, (0.7, 0.5))
        self.assertTrue(capture.mute)
        self.assertTrue(capture.corked)
        self.assertEqual(capture.binary, "linphone")
        self.assertEqual(capture.direction, "capture")

    def test_volume_write_checks_current_identity_and_preserves_channels(self):
        playback = self.backend.streams()[0]
        self.backend.pulse.sink_input_info.return_value = info()
        self.backend.set_volume(playback, (0.2, 0.2))
        self.backend.pulse.sink_input_volume_set.assert_called_once_with(1, [0.2, 0.2])
        self.backend.pulse.sink_input_mute.assert_not_called()

    def test_index_reassigned_to_another_app_is_not_written(self):
        playback = self.backend.streams()[0]
        self.backend.pulse.sink_input_info.return_value = info("Discord")
        with self.assertRaises(BackendError):
            self.backend.set_volume(playback, (0.2, 0.2))
        self.backend.pulse.sink_input_volume_set.assert_not_called()

    def test_configured_target_can_be_written(self):
        self.backend.config = Config(applications=Applications(targets=("firefox",)))
        self.backend.pulse.sink_input_info.return_value = info("firefox")
        self.backend.set_volume(self.backend._stream(info("firefox"), "playback"), (0.1, 0.1))
        self.backend.pulse.sink_input_volume_set.assert_called_once_with(1, [0.1, 0.1])
        with self.assertRaises(BackendError):
            self.backend.set_volume(self.backend._stream(info(), "playback"), (0.1, 0.1))

    def test_reused_target_index_is_rechecked_before_writing(self):
        for changed_field in ("client", "process_id"):
            with self.subTest(changed_field=changed_field):
                playback = self.backend.streams()[0]
                current = info()
                if changed_field == "client":
                    current.client = 99
                else:
                    current.proplist["application.process.id"] = "99"
                self.backend.pulse.sink_input_info.return_value = current
                with self.assertRaises(BackendError):
                    self.backend.set_volume(playback, (0.14, 0.1))
        self.backend.pulse.sink_input_volume_set.assert_not_called()

    def test_channel_count_is_rechecked_before_writing(self):
        playback = self.backend.streams()[0]
        current = info()
        current.volume.values = [0.7]
        self.backend.pulse.sink_input_info.return_value = current
        with self.assertRaises(BackendError):
            self.backend.set_volume(playback, (0.14, 0.1))
        self.backend.pulse.sink_input_volume_set.assert_not_called()

    def test_non_brave_and_capture_writes_are_rejected(self):
        for binary, direction in [("Discord", "playback"), ("linphone", "playback"),
                                  ("brave", "capture")]:
            with self.subTest(binary=binary, direction=direction):
                with self.assertRaises(BackendError):
                    self.backend.set_volume(self.backend._stream(info(binary), direction), (0.2, 0.2))
        self.backend.pulse.sink_input_volume_set.assert_not_called()


@pytest.mark.parametrize("operation", ["sink_input_list", "source_output_list"])
@pytest.mark.parametrize("raises", [False, True])
def test_disconnect_during_enumeration_never_returns_partial_or_empty_list(operation, raises):
    backend = PulseBackend.__new__(PulseBackend)
    backend.api = SimpleNamespace(PulseError=RuntimeError)
    backend.pulse = Mock(connected=True)
    backend.pulse.sink_input_list.return_value = []
    backend.pulse.source_output_list.return_value = []

    def disconnect():
        backend.pulse.connected = False
        if raises:
            raise RuntimeError("connection failed")
        return []

    getattr(backend.pulse, operation).side_effect = disconnect
    with pytest.raises(BackendDisconnected):
        backend.streams()


def test_enumeration_failure_while_connected_is_not_a_disconnect():
    backend = PulseBackend.__new__(PulseBackend)
    backend.api = SimpleNamespace(PulseError=RuntimeError)
    backend.pulse = Mock(connected=True)
    backend.pulse.sink_input_list.side_effect = RuntimeError("permission denied")
    with pytest.raises(BackendError, match="permission denied") as raised:
        backend.streams()
    assert not isinstance(raised.value, BackendDisconnected)


def test_connection_attempt_is_bounded_and_closes_on_failure():
    pulse = Mock()
    pulse.connect.side_effect = RuntimeError("server unavailable")
    api = SimpleNamespace(Pulse=Mock(return_value=pulse), PulseError=RuntimeError)
    with patch.dict("sys.modules", pulsectl=api):
        with pytest.raises(BackendDisconnected, match="server unavailable"):
            PulseBackend()
    api.Pulse.assert_called_once_with("audio-duckd", connect=False)
    pulse.connect.assert_called_once_with(autospawn=False, timeout=2.0)
    pulse.close.assert_called_once_with()


@pytest.mark.parametrize("operation", ["sink_input_info", "sink_input_volume_set"])
@pytest.mark.parametrize("raises", [False, True])
def test_disconnect_during_volume_write_is_reported(operation, raises):
    backend = PulseBackend.__new__(PulseBackend)
    backend.config = Config()
    backend.api = SimpleNamespace(PulseError=RuntimeError, PulseVolumeInfo=list)
    backend.pulse = Mock(connected=True)
    backend.pulse.sink_input_info.return_value = info()

    def disconnect(*args):
        backend.pulse.connected = False
        if raises:
            raise RuntimeError("connection lost during write")
        return info()

    getattr(backend.pulse, operation).side_effect = disconnect
    with pytest.raises(BackendDisconnected):
        backend.set_volume(backend._stream(info(), "playback"), (0.14, 0.1))
    if operation == "sink_input_info":
        backend.pulse.sink_input_volume_set.assert_not_called()


def test_known_disconnect_does_not_attempt_a_volume_write():
    backend = PulseBackend.__new__(PulseBackend)
    backend.config = Config()
    backend.pulse = Mock(connected=False)
    with pytest.raises(BackendDisconnected):
        backend.set_volume(backend._stream(info(), "playback"), (0.14, 0.1))
    backend.pulse.sink_input_info.assert_not_called()
    backend.pulse.sink_input_volume_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
