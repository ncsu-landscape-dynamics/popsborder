"""Test general function used for inputs"""

import pytest

from popsborder.inputs import (
    text_to_value,
)


def test_text_to_value_boolean_json_and_canonical_yaml():
    """Check that JSON representation of boolean values yields booleans"""
    assert text_to_value("true") == True
    assert text_to_value("false") == False


def test_text_to_value_boolean_python_and_extra_yaml():
    """Check that Python-like, non-canonical YAML representation yields booleans"""
    assert text_to_value("True") == True
    assert text_to_value("False") == False


def test_text_to_value_boolean_all_caps_extra_yaml():
    """Check that all caps, non-canonical YAML representation yields booleans"""
    assert text_to_value("TRUE") == True
    assert text_to_value("FALSE") == False


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "Yes",
        "YES",
        "y",
        "Y",
        "no",
        "No",
        "NO",
        "n",
        "N",
        "on",
        "On",
        "ON",
        "off",
        "Off",
        "OFF",
    ],
)
def test_text_to_value_boolean_like_text_still_text(text):
    """Check that old YAML boolean-like text values are still text"""
    assert text_to_value(text) == text


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", 0),
        ("1", 1),
        ("1.", 1.0),
        ("1.0", 1.0),
    ],
)
def test_text_to_value_boolean_like_value_still_value(value, expected):
    """Check that non-text boolean-like values have proper value and type"""
    new_value = text_to_value(value)
    assert new_value == expected
    # Integers and floats 0 and 1 actually compare True against booleans,
    # so we need to check the type as well.
    assert type(new_value) == type(expected)
