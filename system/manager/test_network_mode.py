import pytest
from unittest.mock import MagicMock

NETWORK_MODE_DEFAULT = 0
NETWORK_MODE_PRIVACY = 1
NETWORK_MODE_OFFLINE = 2


def make_params(network_mode=0, bypass_ota=False, bypass_backup=False):
    """Create a mock Params object that returns network mode values."""
    params = MagicMock()
    def get_side_effect(key, **kwargs):
        values = {
            "NetworkMode": network_mode,
        }
        return values.get(key)
    def get_bool_side_effect(key, **kwargs):
        values = {
            "NetworkBypassOTA": bypass_ota,
            "NetworkBypassBackup": bypass_backup,
        }
        return values.get(key, False)
    params.get = get_side_effect
    params.get_bool = get_bool_side_effect
    return params


class TestNetworkModeConditions:

    def _import_conditions(self):
        from openpilot.system.manager.process_config import (
            not_privacy_mode, not_offline_mode, updated_with_bypass,
        )
        return not_privacy_mode, not_offline_mode, updated_with_bypass

    # --- not_privacy_mode (gates uploader, sentry, statsd) ---

    def test_uploader_allowed_in_default_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert not_privacy_mode(True, params, MagicMock()) is True

    def test_uploader_blocked_in_privacy_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert not_privacy_mode(True, params, MagicMock()) is False

    def test_uploader_blocked_in_offline_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert not_privacy_mode(True, params, MagicMock()) is False

    # --- not_offline_mode (gates athenad) ---

    def test_athenad_allowed_in_default_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert not_offline_mode(True, params, MagicMock()) is True

    def test_athenad_allowed_in_privacy_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert not_offline_mode(True, params, MagicMock()) is True

    def test_athenad_blocked_in_offline_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert not_offline_mode(True, params, MagicMock()) is False

    # --- updated_with_bypass ---

    def test_updated_allowed_in_default_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert updated_with_bypass(False, params, MagicMock()) is True

    def test_updated_allowed_in_privacy_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert updated_with_bypass(False, params, MagicMock()) is True

    def test_updated_blocked_in_offline_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert updated_with_bypass(False, params, MagicMock()) is False

    def test_updated_bypass_in_offline_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE, bypass_ota=True)
        assert updated_with_bypass(False, params, MagicMock()) is True
