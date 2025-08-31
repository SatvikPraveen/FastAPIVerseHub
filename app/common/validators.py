# File: app/common/validators.py

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import validator, ValidationError


class ValidationUtils:
    """Utility functions for validation."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str, country_code: Optional[str] = None) -> bool:
        """Validate phone number format."""
        # Remove all non-digit characters
        clean_phone = re.sub(r'\D', '', phone)
        
        # Basic validation for international format
        if country_code == "US":
            return len(clean_phone) == 10 or (len(clean_phone) == 11 and clean_phone.startswith('1'))
        else:
            # International format: 7-15 digits
            return 7 <= len(clean_phone) <= 15
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
        """Validate URL format."""
        if not allowed_schemes:
            allowed_schemes = ['http', 'https']
        
        try:
            result = urlparse(url)
            return (
                result.scheme in allowed_schemes and
                result.netloc and
                len(url) <= 2048
            )
        except Exception:
            return False
    
    @staticmethod
    def validate_slug(slug: str) -> bool:
        """Validate URL slug format."""
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        return bool(re.match(pattern, slug)) and 3 <= len(slug) <= 100
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format."""
        pattern = r'^[a-zA-Z0-9_-]{3,30}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength and return detailed feedback."""
        issues = []
        score = 0
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        else:
            score += 1
        
        if len(password) >= 12:
            score += 1
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        else:
            score += 1
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        else:
            score += 1
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        else:
            score += 1
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        else:
            score += 1
        
        # Check for common patterns
        common_patterns = [
            r'123456', r'password', r'qwerty', r'abc123',
            r'admin', r'letmein', r'welcome', r'monkey'
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password.lower()):
                issues.append("Password contains common patterns")
                score -= 1
                break
        
        # Determine strength
        if score >= 5:
            strength = "strong"
        elif score >= 3:
            strength = "medium"
        else:
            strength = "weak"
        
        return {
            "is_valid": len(issues) == 0,
            "strength": strength,
            "score": max(0, score),
            "issues": issues
        }
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Basic HTML sanitization."""
        # Remove script tags and their content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove potentially dangerous attributes
        text = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bjavascript:', '', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def validate_file_size(file_size: int, max_size: int) -> bool:
        """Validate file size."""
        return 0 < file_size <= max_size
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension."""
        if not filename:
            return False
        
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        return extension in [ext.lower() for ext in allowed_extensions]
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> bool:
        """Validate date range."""
        return start_date <= end_date
    
    @staticmethod
    def validate_age(birth_date: date, min_age: int = 13, max_age: int = 120) -> bool:
        """Validate age based on birth date."""
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return min_age <= age <= max_age


# Custom Pydantic validators
def email_validator(cls, v):
    """Pydantic email validator."""
    if not ValidationUtils.validate_email(v):
        raise ValueError('Invalid email format')
    return v.lower()


def phone_validator(cls, v):
    """Pydantic phone validator."""
    if v and not ValidationUtils.validate_phone(v):
        raise ValueError('Invalid phone number format')
    return v


def url_validator(cls, v):
    """Pydantic URL validator."""
    if v and not ValidationUtils.validate_url(v):
        raise ValueError('Invalid URL format')
    return v


def slug_validator(cls, v):
    """Pydantic slug validator."""
    if not ValidationUtils.validate_slug(v):
        raise ValueError('Invalid slug format. Use lowercase letters, numbers, and hyphens only')
    return v


def username_validator(cls, v):
    """Pydantic username validator."""
    if not ValidationUtils.validate_username(v):
        raise ValueError('Invalid username. Use 3-30 characters: letters, numbers, underscores, hyphens')
    return v


def password_validator(cls, v):
    """Pydantic password validator."""
    validation_result = ValidationUtils.validate_password_strength(v)
    if not validation_result['is_valid']:
        raise ValueError(f"Password validation failed: {'; '.join(validation_result['issues'])}")
    return v


def sanitize_html_validator(cls, v):
    """Pydantic HTML sanitizer validator."""
    if v:
        return ValidationUtils.sanitize_html(v)
    return v


def file_size_validator(max_size: int):
    """Pydantic file size validator factory."""
    def validator_func(cls, v):
        if hasattr(v, 'size') and v.size:
            if not ValidationUtils.validate_file_size(v.size, max_size):
                raise ValueError(f'File size {v.size} exceeds maximum allowed size {max_size}')
        return v
    return validator_func


def file_extension_validator(allowed_extensions: List[str]):
    """Pydantic file extension validator factory."""
    def validator_func(cls, v):
        if hasattr(v, 'filename') and v.filename:
            if not ValidationUtils.validate_file_extension(v.filename, allowed_extensions):
                raise ValueError(f'File extension not allowed. Allowed: {", ".join(allowed_extensions)}')
        return v
    return validator_func


def date_range_validator(end_date_field: str):
    """Pydantic date range validator factory."""
    def validator_func(cls, v, values):
        end_date = values.get(end_date_field)
        if v and end_date and not ValidationUtils.validate_date_range(v, end_date):
            raise ValueError(f'Start date must be before or equal to end date')
        return v
    return validator_func


def age_validator(min_age: int = 13, max_age: int = 120):
    """Pydantic age validator factory."""
    def validator_func(cls, v):
        if v and not ValidationUtils.validate_age(v, min_age, max_age):
            raise ValueError(f'Age must be between {min_age} and {max_age} years')
        return v
    return validator_func


class ContentValidator:
    """Content validation utilities."""
    
    @staticmethod
    def validate_profanity(text: str, strict: bool = False) -> bool:
        """Basic profanity filter."""
        # Simple word list - in production, use a proper profanity filter library
        basic_profanity = [
            'spam', 'scam', 'fake', 'virus', 'malware',
            # Add more as needed
        ]
        
        text_lower = text.lower()
        
        if strict:
            # Exact word matching
            words = re.findall(r'\b\w+\b', text_lower)
            return not any(word in basic_profanity for word in words)
        else:
            # Substring matching
            return not any(word in text_lower for word in basic_profanity)
    
    @staticmethod
    def validate_content_length(
        text: str,
        min_length: int = 0,
        max_length: int = 10000,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate content length and word count."""
        char_count = len(text)
        word_count = len(text.split()) if text else 0
        
        issues = []
        
        if char_count < min_length:
            issues.append(f"Content must be at least {min_length} characters")
        
        if char_count > max_length:
            issues.append(f"Content must not exceed {max_length} characters")
        
        if min_words and word_count < min_words:
            issues.append(f"Content must have at least {min_words} words")
        
        if max_words and word_count > max_words:
            issues.append(f"Content must not exceed {max_words} words")
        
        return {
            "is_valid": len(issues) == 0,
            "char_count": char_count,
            "word_count": word_count,
            "issues": issues
        }
    
    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        """Extract @mentions from text."""
        pattern = r'@([a-zA-Z0-9_]{1,50})'
        return re.findall(pattern, text)
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extract #hashtags from text."""
        pattern = r'#([a-zA-Z0-9_]{1,50})'
        return re.findall(pattern, text)
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(pattern, text)


def content_validator(
    min_length: int = 0,
    max_length: int = 10000,
    check_profanity: bool = False,
    allow_html: bool = False
):
    """Content validator factory for Pydantic."""
    def validator_func(cls, v):
        if not v:
            return v
        
        # Length validation
        validation_result = ContentValidator.validate_content_length(v, min_length, max_length)
        if not validation_result['is_valid']:
            raise ValueError('; '.join(validation_result['issues']))
        
        # Profanity check
        if check_profanity and not ContentValidator.validate_profanity(v):
            raise ValueError('Content contains inappropriate language')
        
        # HTML sanitization
        if not allow_html:
            v = ValidationUtils.sanitize_html(v)
        
        return v
    
    return validator_func