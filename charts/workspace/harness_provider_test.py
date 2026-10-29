"""Focused provider-selection checks; stdlib only."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("kc_harness_under_test",
    Path(__file__).with_name("harness.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class ProviderConfigTest(unittest.TestCase):
    def test_cloud_requires_key_and_model(self):
        with patch.dict(os.environ, {"KC_OLLAMA_CLOUD_API_KEY": "",
                                     "KC_OLLAMA_CLOUD_MODEL": ""}):
            with self.assertRaises(ValueError):
                harness.provider_config("ollama-cloud")

    def test_cloud_is_pinned_to_https(self):
        with patch.dict(os.environ, {"KC_OLLAMA_CLOUD_API_KEY": "dummy",
                                     "KC_OLLAMA_CLOUD_MODEL": "sample-model"}):
            self.assertEqual(harness.provider_config("ollama-cloud"),
                             ("https://ollama.com/v1", "dummy", "sample-model"))

    def test_bedrock_region_validation(self):
        with patch.dict(os.environ, {"KC_BEDROCK_REGION": "localhost:8080",
                                     "KC_BEDROCK_API_KEY": "dummy",
                                     "KC_BEDROCK_MODEL": "sample-model"}):
            with self.assertRaises(ValueError):
                harness.provider_config("bedrock")

    def test_bedrock_endpoint(self):
        with patch.dict(os.environ, {"KC_BEDROCK_REGION": "eu-west-1",
                                     "KC_BEDROCK_API_KEY": "dummy",
                                     "KC_BEDROCK_MODEL": "sample-model"}):
            url, _, _ = harness.provider_config("bedrock")
            self.assertEqual(url, "https://bedrock-runtime.eu-west-1.amazonaws.com/openai/v1")

    def test_unknown_provider_fails_closed(self):
        with self.assertRaises(ValueError):
            harness.provider_config("unknown")


if __name__ == "__main__":
    unittest.main()
