"""Hardware-independent discovery filter smoke tests."""
import unittest
from types import SimpleNamespace

from scratch_link_bleak import WEDO_SERVICE, matches


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.device = SimpleNamespace(name="LPF2 Smart Hub")
        self.advertisement = SimpleNamespace(
            service_uuids=[WEDO_SERVICE],
            local_name="LPF2 Smart Hub",
            manufacturer_data={},
        )

    def test_matching_wedo_service(self):
        self.assertTrue(matches(self.device, self.advertisement, [{"services": [WEDO_SERVICE]}]))

    def test_wrong_service_does_not_match(self):
        self.assertFalse(matches(self.device, self.advertisement, [{"services": ["0000180f-0000-1000-8000-00805f9b34fb"]}]))

    def test_prefix(self):
        self.assertTrue(matches(self.device, self.advertisement, [{"namePrefix": "LPF2"}]))
        self.assertFalse(matches(self.device, self.advertisement, [{"namePrefix": "Other"}]))


if __name__ == "__main__":
    unittest.main()
