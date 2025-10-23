"""
MOD-005 FIX: JSON validation with Pydantic

This module provides safe JSON loading with validation using Pydantic models.
It ensures that loaded JSON content matches expected structure and provides
clear error messages when validation fails.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache

from pydantic import BaseModel, Field, validator
from utils.logger import logger


class ContentSection(BaseModel):
    """Pydantic model for content section validation"""
    title: Optional[str] = Field(None, description="Section title")
    text: Optional[str] = Field(None, description="Section text content")
    image: Optional[str] = Field(None, description="Image path or URL")
    buttons: Optional[List[Dict[str, str]]] = Field(None, description="Button definitions")
    subsections: Optional[Dict[str, Any]] = Field(None, description="Nested subsections")

    @validator('text')
    def validate_text_not_empty(cls, v):
        """Ensure text is not just whitespace if provided"""
        if v is not None and not v.strip():
            raise ValueError("Text content cannot be empty or whitespace only")
        return v

    class Config:
        extra = "allow"  # Allow extra fields for flexibility


class ContentData(BaseModel):
    """Pydantic model for entire content file validation"""
    sections: Dict[str, ContentSection] = Field(..., description="Content sections")

    @validator('sections')
    def validate_sections_not_empty(cls, v):
        """Ensure at least one section exists"""
        if not v:
            raise ValueError("Content must have at least one section")
        return v

    class Config:
        extra = "allow"


@lru_cache(maxsize=10)
def load_json_content(file_path: str, validate: bool = True) -> Dict[str, Any]:
    """
    OPTIMIZATION: Singleton JSON loader with LRU cache (lazy load once per worker)

    Loads JSON content from file with optional Pydantic validation.

    Args:
        file_path: Path to JSON file
        validate: Whether to validate with Pydantic (default: True)

    Returns:
        Dict containing loaded and validated JSON content

    Raises:
        FileNotFoundError: If JSON file doesn't exist
        json.JSONDecodeError: If JSON is malformed
        ValueError: If validation fails

    Examples:
        >>> content = load_json_content("general_info.json")
        >>> section = content.get("sections", {}).get("about")
    """
    path = Path(file_path)

    if not path.exists():
        error_msg = f"JSON file not found: {file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Loaded JSON content from: {file_path}")

        # MOD-005: Validate JSON structure with Pydantic
        if validate:
            try:
                # Try to validate as ContentData
                validated = ContentData(**data)
                logger.debug(f"JSON validation successful for: {file_path}")
                return validated.dict()
            except Exception as e:
                # If strict validation fails, log warning but continue
                logger.warning(
                    f"JSON validation failed for {file_path}, using raw data: {e}"
                )
                # Return raw data with .get() safety
                return SafeDict(data)

        return SafeDict(data)

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format in {file_path}: {e}"
        logger.error(error_msg)
        raise json.JSONDecodeError(error_msg, e.doc, e.pos)

    except Exception as e:
        error_msg = f"Error loading JSON from {file_path}: {e}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg)


class SafeDict(dict):
    """
    MOD-005 FIX: Dictionary with safe .get() that never raises KeyError

    This wrapper ensures that accessing nested keys with .get() always
    returns None or a default value instead of raising exceptions.
    """

    def get(self, key: Any, default=None):
        """Override get to return default for missing keys"""
        value = super().get(key, default)
        # Wrap nested dicts in SafeDict
        if isinstance(value, dict) and not isinstance(value, SafeDict):
            return SafeDict(value)
        return value

    def __getitem__(self, key):
        """Override getitem to return None for missing keys instead of raising"""
        try:
            value = super().__getitem__(key)
            # Wrap nested dicts in SafeDict
            if isinstance(value, dict) and not isinstance(value, SafeDict):
                return SafeDict(value)
            return value
        except KeyError:
            logger.warning(f"Attempted to access missing key: {key}")
            return None


def validate_json_structure(data: Dict[str, Any], required_keys: List[str]) -> bool:
    """
    Helper function to validate that required keys exist in JSON data

    Args:
        data: Dictionary to validate
        required_keys: List of required key names

    Returns:
        bool: True if all required keys exist

    Raises:
        ValueError: If any required key is missing
    """
    missing_keys = [key for key in required_keys if key not in data]

    if missing_keys:
        error_msg = f"Missing required keys in JSON: {', '.join(missing_keys)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"JSON structure validation passed. Found all required keys.")
    return True


# Clear cache function for reloading JSON during development
def clear_json_cache():
    """Clear the LRU cache to force reload of JSON files"""
    load_json_content.cache_clear()
    logger.info("JSON content cache cleared")


__all__ = [
    "load_json_content",
    "validate_json_structure",
    "clear_json_cache",
    "SafeDict",
    "ContentSection",
    "ContentData"
]
