"""Launcher recovery tests; never start or stop real user processes."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'runtime').mkdir()
        (self.root / 'runtime' / 'ollama.exe').touch()
        self.root_patch = patch.object(launch, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_existing_app_and_ai_reused_without_spawning(self):
        with patch.object(launch, 'ready', return_value=True), \
             patch.object(launch.subprocess, 'Popen') as spawn, \
             patch.object(launch.webbrowser, 'open') as browser:
            launch.main()
        spawn.assert_not_called()
        browser.assert_called_once_with('http://127.0.0.1:8765')

    def test_missing_ai_restarted_when_app_is_already_running(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(launch, 'ready', side_effect=[True, False, True, False]), \
             patch.object(launch.subprocess, 'Popen', return_value=process) as spawn, \
             patch.object(launch.webbrowser, 'open') as browser:
            launch.main()
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(spawn.call_args.args[0][-1], 'serve')
        self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_NO_CLOUD'], 'true')
        browser.assert_called_once()
        process.terminate.assert_called_once()

    def test_startup_waits_for_ai_before_opening_new_app(self):
        ai, server = Mock(), Mock()
        ai.poll.return_value = None
        server.poll.return_value = None
        events = []

        def readiness(url):
            events.append(url)
            # Existing app absent, local AI absent, then both become ready.
            return len(events) >= 3

        with patch.object(launch, 'ready', side_effect=readiness), \
             patch.object(launch.subprocess, 'Popen', side_effect=[ai, server]) as spawn, \
             patch.object(launch.webbrowser, 'open', side_effect=lambda url: events.append('browser')):
            launch.main()
        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(events[-1], 'browser')
        self.assertEqual(events[2], 'http://127.0.0.1:11434/api/tags')
        server.wait.assert_called()
        ai.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
