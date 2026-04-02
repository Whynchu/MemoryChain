"""
Answer parser service for converting natural language responses to typed values.

Handles common user responses to questionnaire questions:
- Numeric: "7", "7.5", "seven" -> float
- Scale: "8/10", "8 out of 10", "8" -> int  
- Boolean: "yes", "no", "true", "false" -> bool
- Text: any string -> str
- Choice: validates against allowed options
"""

import re
from typing import Any, Union

from ..schemas import QuestionType


class AnswerParsingError(Exception):
    """Raised when answer cannot be parsed for the expected question type."""
    pass


def parse_answer(raw_text: str, question_type: QuestionType, **kwargs) -> Any:
    """
    Parse a natural language answer based on the question type.
    
    Args:
        raw_text: The user's raw response
        question_type: Expected type (numeric, scale, boolean, text, choice)
        **kwargs: Additional parsing context:
            - choices: list[str] for choice questions
            - min_value, max_value: float for numeric/scale validation
    
    Returns:
        Parsed value in the appropriate type
        
    Raises:
        AnswerParsingError: If the answer cannot be parsed or is invalid
    """
    text = raw_text.strip().lower()
    
    if question_type == "numeric":
        return _parse_numeric(text, kwargs.get("min_value"), kwargs.get("max_value"))
    elif question_type == "scale": 
        return _parse_scale(text, kwargs.get("min_value", 1), kwargs.get("max_value", 10))
    elif question_type == "boolean":
        return _parse_boolean(text)
    elif question_type == "choice":
        choices = kwargs.get("choices", [])
        return _parse_choice(text, choices)
    elif question_type == "text":
        return raw_text.strip()  # Preserve original case for text
    else:
        raise AnswerParsingError(f"Unknown question type: {question_type}")


def _parse_numeric(text: str, min_value: float | None = None, max_value: float | None = None) -> float:
    """Parse numeric values like '7', '7.5', 'seven', '~7 hours'."""
    
    # Handle word numbers first
    word_numbers = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    if text in word_numbers:
        value = float(word_numbers[text])
    else:
        # Extract numeric value with regex
        # Matches: "7", "7.5", "~7", "7 hours", "7.5 kg", etc.
        match = re.search(r'[~]?(\d+(?:\.\d+)?)', text)
        if not match:
            raise AnswerParsingError(f"No numeric value found in '{text}'")
        
        value = float(match.group(1))
    
    # Validate range if provided
    if min_value is not None and value < min_value:
        raise AnswerParsingError(f"Value {value} is below minimum {min_value}")
    if max_value is not None and value > max_value:
        raise AnswerParsingError(f"Value {value} is above maximum {max_value}")
        
    return value


def _parse_scale(text: str, min_value: int = 1, max_value: int = 10) -> int:
    """Parse scale values like '8/10', '8 out of 10', '8'."""
    
    # Handle "X/Y" or "X out of Y" format
    fraction_match = re.search(r'(\d+)\s*(?:/|out of)\s*(\d+)', text)
    if fraction_match:
        numerator = int(fraction_match.group(1))
        denominator = int(fraction_match.group(2))
        
        # Convert to target scale
        if denominator != max_value:
            value = round((numerator / denominator) * max_value)
        else:
            value = numerator
    else:
        # Try to extract a simple number
        try:
            value = int(_parse_numeric(text))
        except AnswerParsingError:
            raise AnswerParsingError(f"Cannot parse scale value from '{text}'")
    
    # Validate range
    if value < min_value or value > max_value:
        raise AnswerParsingError(f"Scale value {value} is outside range {min_value}-{max_value}")
        
    return value


def _parse_boolean(text: str) -> bool:
    """Parse boolean values like 'yes', 'no', 'true', 'false'."""
    
    true_values = {'yes', 'y', 'true', 't', '1', 'on', 'enabled', 'good', 'ok', 'okay'}
    false_values = {'no', 'n', 'false', 'f', '0', 'off', 'disabled', 'bad', 'nope'}
    
    if text in true_values:
        return True
    elif text in false_values:
        return False
    else:
        raise AnswerParsingError(f"Cannot parse boolean value from '{text}' (expected yes/no, true/false, etc.)")


def _parse_choice(text: str, choices: list[str]) -> str:
    """Parse choice values by matching against allowed options."""
    
    if not choices:
        raise AnswerParsingError("No choices provided for choice question")
    
    # Try exact match first (case-insensitive)
    for choice in choices:
        if text == choice.lower():
            return choice
    
    # Try partial match
    matches = [choice for choice in choices if text in choice.lower() or choice.lower() in text]
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise AnswerParsingError(f"Ambiguous choice '{text}' matches multiple options: {matches}")
    else:
        raise AnswerParsingError(f"Choice '{text}' does not match any of: {choices}")


def validate_parsed_answer(value: Any, question_type: QuestionType, **kwargs) -> bool:
    """
    Validate that a parsed answer meets the question's constraints.
    
    Returns True if valid, False otherwise.
    """
    try:
        if question_type == "numeric":
            min_val = kwargs.get("min_value")
            max_val = kwargs.get("max_value") 
            return (min_val is None or value >= min_val) and (max_val is None or value <= max_val)
        elif question_type == "scale":
            min_val = kwargs.get("min_value", 1)
            max_val = kwargs.get("max_value", 10)
            return min_val <= value <= max_val
        elif question_type == "choice":
            choices = kwargs.get("choices", [])
            return value in choices
        else:
            return True  # text and boolean are always valid once parsed
    except:
        return False