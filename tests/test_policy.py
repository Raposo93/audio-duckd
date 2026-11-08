from dataclasses import replace
import unittest

from audio_duckd.backend import BackendError, Stream
from audio_duckd.policy import DuckingPolicy
from audio_duckd.config import Applications, Config


def stream(index, binary, volumes=(0.8, 0.6), **kwargs):
    return Stream(index, "playback", binary, index + 100, str(index), volumes, **kwargs)


class FakeBackend:
    def __init__(self, *streams):
        self.items = list(streams)
        self.writes = []
        self.fail = False

    def streams(self):
        return list(self.items)

    def set_volume(self, target, volumes):
        if self.fail:
            raise BackendError("simulated failure")
        self.writes.append((target.binary, target.index, volumes))
        self.items = [replace(s, volumes=volumes) if s.identity == target.identity else s
                      for s in self.items]


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.brave = stream(1, "brave")
        self.linphone = stream(2, "linphone", mute=True, corked=True)
        self.discord = stream(3, "Discord")
        self.backend = FakeBackend(self.brave, self.discord)
        self.policy = DuckingPolicy(self.backend)

    def test_custom_selectors_and_multiple_targets(self):
        config = Config(applications=Applications(
            linphone=("phone",), discord=("chat",), targets=("music", "browser")),
            attenuation_factor=0.5)
        backend = FakeBackend(stream(1, "music"), stream(2, "browser"),
                              stream(3, "phone"), stream(4, "chat"), stream(5, "brave"))
        policy = DuckingPolicy(backend, config)
        policy.refresh()
        self.assertEqual(backend.writes, [("music", 1, (0.4, 0.3)),
                                          ("browser", 2, (0.4, 0.3))])
        policy.refresh(restoring=True)
        self.assertEqual(backend.items[0].volumes, (0.8, 0.6))

    def test_factor_limits_low_volume_and_no_compounding(self):
        for factor in (0, 0.2, 1):
            with self.subTest(factor=factor):
                backend = FakeBackend(stream(1, "brave", (0.1, 0.05)), self.linphone)
                policy = DuckingPolicy(backend, Config(attenuation_factor=factor))
                policy.refresh()
                policy.refresh()
                self.assertEqual(backend.items[0].volumes, (0.1 * factor, 0.05 * factor))
                policy.refresh(restoring=True)
                self.assertEqual(backend.items[0].volumes, (0.1, 0.05))

    def test_channel_count_change_does_not_apply_a_partial_comparison(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items[0] = replace(self.backend.items[0], volumes=(0.8 * 0.2,))
        self.policy.refresh()
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual(self.policy.saved[self.brave.identity], self.brave.volumes)

    def test_enter_hold_and_leave_activity_restores_each_channel(self):
        self.policy.refresh()
        self.assertEqual(self.backend.writes, [])
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.policy.refresh()
        self.assertEqual(self.backend.writes, [("brave", 1, (0.8 * 0.2, 0.6 * 0.2))])
        self.backend.items = [s for s in self.backend.items if s.binary != "linphone"]
        self.policy.refresh()
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8, 0.6)))
        self.assertEqual(self.policy.saved, {})

    def test_channel_count_change_blocks_restore_until_original_layout_returns(self):
        for restoring in (False, True):
            with self.subTest(restoring=restoring):
                backend = FakeBackend(self.brave, self.linphone)
                policy = DuckingPolicy(backend)
                policy.refresh()
                backend.items = [replace(self.brave, volumes=(0.1,))]
                policy.refresh(restoring=restoring)
                self.assertEqual(len(backend.writes), 1)
                self.assertEqual(backend.items[0].volumes, (0.1,))
                backend.items[0] = replace(self.brave, volumes=(0.1, 0.1))
                policy.refresh(restoring=restoring)
                self.assertEqual(backend.items[0].volumes, self.brave.volumes)
                self.assertEqual(policy.saved, {})

    def test_each_surviving_stream_restores_independently_and_keeps_current_mute(self):
        first = replace(self.brave, mute=True)
        second = stream(4, "brave", (0.1, 0.05))
        vanished = stream(5, "brave", (0.3,))
        backend = FakeBackend(first, second, vanished, self.linphone)
        policy = DuckingPolicy(backend)
        policy.refresh()
        self.assertEqual([s.volumes for s in backend.items[:3]],
                         [(0.8 * 0.2, 0.6 * 0.2), (0.1 * 0.2, 0.05 * 0.2), (0.3 * 0.2,)])
        self.assertTrue(backend.items[0].mute)
        self.assertFalse(backend.items[1].mute)
        # Manual mute changes must survive restoration too.
        backend.items = [replace(backend.items[0], mute=False),
                         replace(backend.items[1], mute=True)]
        policy.refresh()
        self.assertEqual(backend.writes[-2:], [("brave", 1, first.volumes),
                                               ("brave", 4, second.volumes)])
        self.assertFalse(backend.items[0].mute)
        self.assertTrue(backend.items[1].mute)
        self.assertEqual(policy.saved, {})

    def test_silence_and_microphone_mute_do_not_end_activity(self):
        capture = replace(self.linphone, direction="capture")
        self.backend.items.append(capture)
        self.policy.refresh()
        self.backend.items[-1] = replace(capture, mute=False, corked=False)
        self.policy.refresh()
        self.backend.items[-1] = replace(capture, mute=True, corked=True)
        self.policy.refresh()
        self.assertEqual(self.backend.writes, [("brave", 1, (0.8 * 0.2, 0.6 * 0.2))])
        self.assertTrue(self.policy.saved)

    def test_discord_and_linphone_are_never_written(self):
        self.backend.items.extend([self.linphone, replace(self.brave, direction="capture")])
        self.policy.refresh()
        self.policy.refresh(restoring=True)
        self.assertTrue(all(binary == "brave" for binary, _, _ in self.backend.writes))
        self.assertEqual(self.backend.items[1], self.discord)
        self.assertEqual(self.backend.items[2], self.linphone)
        self.assertEqual(self.backend.items[3], replace(self.brave, direction="capture"))

    def test_new_brave_stream_during_call_has_its_own_original_volume(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items.append(stream(4, "brave", (0.4,)))
        self.policy.refresh()
        self.policy.refresh(restoring=True)
        self.assertIn(("brave", 1, (0.8, 0.6)), self.backend.writes)
        self.assertIn(("brave", 4, (0.4,)), self.backend.writes)

    def test_manual_changes_are_ducked_again_without_losing_original(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items[0] = replace(self.brave, volumes=(0.9, 0.9))
        self.policy.refresh()
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8 * 0.2, 0.6 * 0.2)))
        self.policy.refresh(restoring=True)
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8, 0.6)))

    def test_disappeared_stream_does_not_transfer_volume_to_replacement(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items = [stream(9, "brave", (0.3, 0.3))]
        self.policy.refresh()
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual(self.policy.saved, {})

    def test_reused_index_does_not_restore_discord(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items = [stream(1, "Discord")]
        self.policy.refresh()
        self.assertEqual(len(self.backend.writes), 1)

    def test_reused_index_for_new_brave_client_gets_new_original(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items[0] = replace(self.brave, client=500, volumes=(0.3, 0.4))
        self.policy.refresh()
        self.policy.refresh(restoring=True)
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.3, 0.4)))

    def test_failed_duck_is_retried_without_saving_unmodified_stream(self):
        self.backend.items.append(self.linphone)
        self.backend.fail = True
        self.policy.refresh()
        self.assertEqual(self.policy.saved, {})
        self.backend.fail = False
        self.policy.refresh()
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8 * 0.2, 0.6 * 0.2)))

    def test_failed_restore_is_retried(self):
        self.backend.items.append(self.linphone)
        self.policy.refresh()
        self.backend.items = self.backend.items[:2]
        self.backend.fail = True
        self.policy.refresh()
        self.assertTrue(self.policy.saved)
        self.backend.fail = False
        self.policy.refresh()
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8, 0.6)))
        self.assertEqual(self.policy.saved, {})

    def test_multiple_linphone_streams_require_last_stream_to_disappear(self):
        self.backend.items.extend([self.linphone, replace(self.linphone, index=8)])
        self.policy.refresh()
        self.backend.items.pop()
        self.policy.refresh()
        self.assertEqual(len(self.backend.writes), 1)
        self.backend.items.pop()
        self.policy.refresh()
        self.assertEqual(self.backend.writes[-1], ("brave", 1, (0.8, 0.6)))


if __name__ == "__main__":
    unittest.main()
