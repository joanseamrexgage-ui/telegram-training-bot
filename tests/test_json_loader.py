"""
Unit tests for JSON loader utility

Run with: pytest tests/test_json_loader.py -v
"""

import pytest
import json
from pathlib import Path

from utils.json_loader import (
    load_json_content,
    validate_json_structure,
    SafeDict,
    ContentSection,
    ContentData
)


@pytest.fixture
def sample_json_file(tmp_path):
    """Create a sample JSON file for testing"""
    json_file = tmp_path / "test_content.json"
    content = {
        "sections": {
            "about": {
                "title": "About Us",
                "text": "This is about us section",
                "buttons": [
                    {"text": "Learn More", "callback_data": "learn_more"}
                ]
            },
            "contact": {
                "title": "Contact",
                "text": "Contact information here"
            }
        }
    }

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    return json_file


@pytest.fixture
def invalid_json_file(tmp_path):
    """Create an invalid JSON file for testing"""
    json_file = tmp_path / "invalid.json"

    with open(json_file, 'w') as f:
        f.write("{invalid json content")

    return json_file


def test_load_json_content_success(sample_json_file):
    """Test loading valid JSON content"""
    content = load_json_content(str(sample_json_file), validate=False)

    assert content is not None
    assert "sections" in content
    assert "about" in content["sections"]
    assert content["sections"]["about"]["title"] == "About Us"


def test_load_json_content_file_not_found():
    """Test loading non-existent JSON file"""
    with pytest.raises(FileNotFoundError):
        load_json_content("/non/existent/file.json")


def test_load_json_content_invalid_json(invalid_json_file):
    """Test loading invalid JSON file"""
    with pytest.raises(json.JSONDecodeError):
        load_json_content(str(invalid_json_file), validate=False)


def test_safe_dict_get():
    """Test SafeDict.get() method"""
    data = SafeDict({
        "key1": "value1",
        "nested": {
            "key2": "value2"
        }
    })

    # Test normal get
    assert data.get("key1") == "value1"

    # Test nested get returns SafeDict
    nested = data.get("nested")
    assert isinstance(nested, SafeDict)
    assert nested.get("key2") == "value2"

    # Test missing key returns None
    assert data.get("missing_key") is None

    # Test missing key with default
    assert data.get("missing_key", "default") == "default"


def test_safe_dict_getitem():
    """Test SafeDict.__getitem__() method"""
    data = SafeDict({
        "key1": "value1",
        "nested": {
            "key2": "value2"
        }
    })

    # Test normal access
    assert data["key1"] == "value1"

    # Test nested access returns SafeDict
    assert isinstance(data["nested"], SafeDict)

    # Test missing key returns None (doesn't raise KeyError)
    assert data["missing_key"] is None


def test_content_section_validation():
    """Test ContentSection Pydantic model validation"""
    # Valid section
    section = ContentSection(
        title="Test Title",
        text="Test content",
        buttons=[{"text": "Click me", "callback_data": "action"}]
    )

    assert section.title == "Test Title"
    assert section.text == "Test content"

    # Section with empty text should raise error
    with pytest.raises(ValueError):
        ContentSection(title="Test", text="   ")


def test_content_data_validation():
    """Test ContentData Pydantic model validation"""
    # Valid content data
    data = ContentData(
        sections={
            "section1": ContentSection(title="Title 1", text="Text 1")
        }
    )

    assert "section1" in data.sections

    # Empty sections should raise error
    with pytest.raises(ValueError):
        ContentData(sections={})


def test_validate_json_structure():
    """Test validate_json_structure helper function"""
    data = {
        "required_key_1": "value1",
        "required_key_2": "value2",
        "optional_key": "value3"
    }

    # Should pass with all required keys present
    result = validate_json_structure(data, ["required_key_1", "required_key_2"])
    assert result is True

    # Should fail with missing keys
    with pytest.raises(ValueError, match="Missing required keys"):
        validate_json_structure(data, ["required_key_1", "missing_key"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
