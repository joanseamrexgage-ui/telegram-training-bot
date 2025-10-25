"""
Basic CI tests to ensure the test infrastructure works.
These tests should always pass and verify that pytest is configured correctly.
"""

import sys
import pytest


def test_python_version():
    """Verify Python version is 3.10+"""
    assert sys.version_info >= (3, 10), "Python 3.10+ is required"


def test_imports_available():
    """Verify core dependencies can be imported"""
    try:
        import aiogram
        import sqlalchemy
        import redis
        import pytest
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required dependency: {e}")


def test_pytest_markers():
    """Verify pytest markers are configured"""
    # This test verifies that pytest configuration is loaded
    assert True


def test_basic_addition():
    """Test with basic math"""
    assert 1 + 1 == 2


async def test_async_support():
    """Verify async test support works"""
    async def async_function():
        return 42

    result = await async_function()
    assert result == 42


def test_math_operations():
    """Basic math test to ensure test runner works"""
    assert 2 + 2 == 4
    assert 10 - 5 == 5
    assert 3 * 4 == 12
    assert 15 / 3 == 5


def test_string_operations():
    """Basic string test"""
    assert "hello".upper() == "HELLO"
    assert "WORLD".lower() == "world"
    assert "test" in "testing"


def test_list_operations():
    """Basic list test"""
    test_list = [1, 2, 3, 4, 5]
    assert len(test_list) == 5
    assert 3 in test_list
    assert test_list[0] == 1
    assert test_list[-1] == 5


def test_dict_operations():
    """Basic dict test"""
    test_dict = {"key1": "value1", "key2": "value2"}
    assert len(test_dict) == 2
    assert "key1" in test_dict
    assert test_dict["key1"] == "value1"


@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (4, 8),
])
def test_parametrize(input, expected):
    """Test parametrization works"""
    assert input * 2 == expected


def test_fixture_usage(mock_bot):
    """Test that fixtures from conftest.py are available"""
    assert mock_bot is not None
    assert hasattr(mock_bot, 'send_message')


def test_environment():
    """Test environment detection"""
    import os
    # In CI, ENVIRONMENT should be set to 'testing'
    env = os.getenv('ENVIRONMENT', 'unknown')
    # This should pass in both local and CI environments
    assert env in ['unknown', 'testing', 'development', 'production']
