import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audio_duckd.__main__ import main
from audio_duckd.config import Applications, Config, ConfigError, DiscordConfig, load_config


class ConfigTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_config(path)

    def test_defaults_and_example(self):
        defaults = Config()
        self.assertEqual(self.load({}), defaults)
        self.assertEqual(load_config(), defaults)
        self.assertEqual(defaults.applications.targets, ("brave",))
        self.assertEqual(defaults.attenuation_factor, 0.2)
        example = Path(__file__).resolve().parents[1] / "config.example.json"
        self.assertEqual(load_config(example), defaults)
        self.assertEqual(self.load(asdict(defaults)), defaults)

    def test_partial_config(self):
        config = self.load({"applications": {"targets": ["firefox", "mpv"]},
                            "discord": {"release_seconds": 2}, "attenuation_factor": 0.5})
        self.assertEqual(config.applications.targets, ("firefox", "mpv"))
        self.assertEqual(config.applications.linphone, ("linphone",))
        self.assertEqual(config.discord.release_seconds, 2)

    def test_factor_bounds_and_types(self):
        for factor in (0, 1, 0.2):
            self.assertEqual(self.load({"attenuation_factor": factor}).attenuation_factor, factor)
        for factor in (-0.01, 1.01, True, None, "0.2", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(factor=factor), self.assertRaises(ConfigError):
                self.load({"attenuation_factor": factor})

    def test_contradictory_selectors(self):
        for apps in ({"targets": ["linphone"]}, {"targets": ["Discord"]},
                     {"linphone": ["same"], "discord": ["same"]},
                     {"discord": ["chat"], "targets": ["brave", "chat"]}):
            with self.subTest(apps=apps), self.assertRaisesRegex(ConfigError, "disjoint"):
                self.load({"applications": apps})

    def test_invalid_selectors(self):
        for values in ([], "brave", None, [True], [""], [" brave"], ["/usr/bin/brave"],
                       ["br*"], ["br?ve"], ["br[av]e"], ["brave (deleted)"], ["brave", "brave"]):
            with self.subTest(values=values), self.assertRaises(ConfigError):
                self.load({"applications": {"targets": values}})

    def test_exact_case_sensitive_selectors(self):
        config = Config(applications=Applications(targets=("discord",)))
        self.assertTrue(config.is_target("discord"))
        self.assertFalse(config.is_target("Discord"))
        self.assertFalse(config.is_target("linphone"))
        self.assertFalse(config.is_target("brave"))

    def test_discord_limits(self):
        self.load({"discord": {"activation_threshold_dbfs": 0,
                               "deactivation_threshold_dbfs": 0,
                               "attack_seconds": 0, "release_seconds": 0}})
        invalid = [{"activation_threshold_dbfs": 1}, {"deactivation_threshold_dbfs": -30},
                   {"attack_seconds": -1}, {"release_seconds": -1},
                   {"sample_interval_seconds": 0}, {"sample_interval_seconds": -1}]
        for key in asdict(DiscordConfig()):
            for value in (True, None, "1", float("nan"), float("inf"), -float("inf")):
                invalid.append({key: value})
        for settings in invalid:
            with self.subTest(settings=settings), self.assertRaises(ConfigError):
                self.load({"discord": settings})

    def test_unknown_fields_and_wrong_structures(self):
        for data in ([], None, {"typo": 1}, {"applications": []}, {"discord": None},
                     {"applications": {"target": ["brave"]}}, {"discord": {"threshold": -40}}):
            with self.subTest(data=data), self.assertRaises(ConfigError):
                self.load(data)

    def test_unreadable_malformed_and_duplicate_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with self.assertRaises(ConfigError):
                load_config(path)
            for content in (b"{", b"\xff", b'{"attenuation_factor": 0.2, "attenuation_factor": 1}',
                            b'{"discord": {"attack_seconds": 0, "attack_seconds": 1}}'):
                path.write_bytes(content)
                with self.subTest(content=content), self.assertRaises(ConfigError):
                    load_config(path)

    def test_invalid_config_fails_before_backend_even_with_inspect(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"attenuation_factor": 2}', encoding="utf-8")
            for extra in ([], ["--inspect"]):
                with patch("sys.argv", ["audio-duckd", "--config", str(path), *extra]), \
                     patch("audio_duckd.__main__.PulseBackend") as backend, \
                     contextlib.redirect_stderr(io.StringIO()) as error, \
                     self.assertRaises(SystemExit) as raised:
                    main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("attenuation_factor", error.getvalue())
                backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
