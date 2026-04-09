"""Unit tests for plugin interface compliance — no real credentials needed."""
import pytest
from base_plugin import BasePlugin
from plugins import all_plugins


def test_all_plugins_instantiate():
    """Every plugin in the registry must instantiate without error."""
    plugins = all_plugins()
    assert isinstance(plugins, list)


def test_all_plugins_inherit_base():
    for plugin in all_plugins():
        assert isinstance(plugin, BasePlugin), f"{type(plugin).__name__} must inherit BasePlugin"


def test_all_plugins_have_name():
    for plugin in all_plugins():
        assert isinstance(plugin.name, str) and plugin.name, f"{type(plugin).__name__}.name must be a non-empty string"


def test_all_plugins_have_credential_keys():
    for plugin in all_plugins():
        assert isinstance(plugin.credential_keys, list), f"{type(plugin).__name__}.credential_keys must be a list"


def test_unavailable_plugins_return_empty():
    """Plugins without credentials must return [] from run_scan, not raise."""
    for plugin in all_plugins():
        if not plugin.is_available():
            result = plugin.run_scan()
            assert result == [], f"{type(plugin).__name__}.run_scan() must return [] when unavailable, got {result}"


def test_finding_format():
    """The _finding helper must produce the correct schema."""
    from plugins.aws_plugin import AWSPlugin
    p = AWSPlugin()
    f = p._finding("test/resource", "HIGH", "security", "Test finding", "Test recommendation", {"key": "val"})
    assert f["platform"] == "aws"
    assert f["severity"] == "HIGH"
    assert f["category"] == "security"
    assert "resource" in f
    assert "finding" in f
    assert "recommendation" in f
    assert "evidence" in f
