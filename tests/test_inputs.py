"""Test general function used for inputs"""

import pytest

from popsborder.inputs import text_to_value


def test_text_to_value_boolean_json_and_canonical_yaml():
    """Check that JSON representation of boolean values yields booleans"""
    assert text_to_value("true") is True
    assert text_to_value("false") is False


def test_text_to_value_boolean_python_and_extra_yaml():
    """Check that Python-like, non-canonical YAML representation yields booleans"""
    assert text_to_value("True") is True
    assert text_to_value("False") is False


def test_text_to_value_boolean_all_caps_extra_yaml():
    """Check that all caps, non-canonical YAML representation yields booleans"""
    assert text_to_value("TRUE") is True
    assert text_to_value("FALSE") is False


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
    "value,expected", [("0", 0), ("1", 1), ("1.", 1.0), ("1.0", 1.0)]
)
def test_text_to_value_boolean_like_value_still_value(value, expected):
    """Check that non-text boolean-like values have proper value and type"""
    new_value = text_to_value(value)
    print(new_value, type(new_value))
    assert new_value == expected
    # Integers and floats 0 and 1 actually compare True against booleans,
    # so we need to check the type as well.
    assert isinstance(new_value, type(expected))
    # We are allow for inheritance in the type check, however
    # the class bool inherits from int, so we need to check that it is not bool.
    assert not isinstance(new_value, bool)
