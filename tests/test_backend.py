from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from audio_duckd.backend import BackendError, PulseBackend


def info(binary="brave", index=1):
    return SimpleNamespace(
        index=index, client=23, mute=True, corked=True,
        proplist={"application.process.binary": binary, "application.process.id": "42"},
        volume=SimpleNamespace(values=[0.7, 0.5]),
    )


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = PulseBackend.__new__(PulseBackend)
        self.backend.api = SimpleNamespace(PulseError=RuntimeError, PulseVolumeInfo=list)
        self.backend.pulse = Mock()
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

    def test_non_brave_and_capture_writes_are_rejected(self):
        for binary, direction in [("Discord", "playback"), ("linphone", "playback"),
                                  ("brave", "capture")]:
            with self.subTest(binary=binary, direction=direction):
                with self.assertRaises(BackendError):
                    self.backend.set_volume(self.backend._stream(info(binary), direction), (0.2, 0.2))
        self.backend.pulse.sink_input_volume_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
