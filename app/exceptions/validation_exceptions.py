# File: app/exceptions/validation_exceptions.py

from typing import Any, Dict, List, Optional
from app.exceptions.base_exceptions import BadRequestException, UnprocessableEntityException


class ValidationException(UnprocessableEntityException):
    """Base exception for validation errors."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        if field:
            details["field"] = field
        
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )


class FieldValidationException(ValidationException):
    """Exception for field-specific validation errors."""
    
    def __init__(
        self,
        field: str,
        message: str,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Validation failed for field '{field}': {message}",
            field=field,
            value=value,
            details=details
        )


class MultipleFieldValidationException(ValidationException):
    """Exception for multiple field validation errors."""
    
    def __init__(
        self,
        errors: List[Dict[str, Any]],
        message: str = "Multiple validation errors occurred",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        details["field_errors"] = errors
        details["error_count"] = len(errors)
        
        super().__init__(
            message=message,
            details=details
        )


class RequiredFieldException(FieldValidationException):
    """Exception for missing required fields."""
    
    def __init__(
        self,
        field: str,
        message: Optional[str] = None
    ):
        if message is None:
            message = "This field is required"
        
        super().__init__(
            field=field,
            message=message
        )


class InvalidEmailException(FieldValidationException):
    """Exception for invalid email addresses."""
    
    def __init__(
        self,
        email: str,
        field: str = "email",
        message: str = "Invalid email format"
    ):
        super().__init__(
            field=field,
            message=message,
            value=email
        )


class InvalidURLException(FieldValidationException):
    """Exception for invalid URLs."""
    
    def __init__(
        self,
        url: str,
        field: str = "url",
        message: str = "Invalid URL format"
    ):
        super().__init__(
            field=field,
            message=message,
            value=url
        )


class InvalidPhoneException(FieldValidationException):
    """Exception for invalid phone numbers."""
    
    def __init__(
        self,
        phone: str,
        field: str = "phone",
        message: str = "Invalid phone number format"
    ):
        super().__init__(
            field=field,
            message=message,
            value=phone
        )


class StringLengthException(FieldValidationException):
    """Exception for string length violations."""
    
    def __init__(
        self,
        field: str,
        value: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ):
        current_length = len(value)
        
        if min_length is not None and current_length < min_length:
            message = f"Must be at least {min_length} characters long (current: {current_length})"
        elif max_length is not None and current_length > max_length:
            message = f"Must not exceed {max_length} characters (current: {current_length})"
        else:
            message = f"Invalid length: {current_length}"
        
        details = {
            "current_length": current_length,
            "min_length": min_length,
            "max_length": max_length
        }
        
        super().__init__(
            field=field,
            message=message,
            value=value,
            details=details
        )


class NumericRangeException(FieldValidationException):
    """Exception for numeric range violations."""
    
    def __init__(
        self,
        field: str,
        value: float,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ):
        if min_value is not None and value < min_value:
            message = f"Must be at least {min_value} (current: {value})"
        elif max_value is not None and value > max_value:
            message = f"Must not exceed {max_value} (current: {value})"
        else:
            message = f"Value out of range: {value}"
        
        details = {
            "current_value": value,
            "min_value": min_value,
            "max_value": max_value
        }
        
        super().__init__(
            field=field,
            message=message,
            value=value,
            details=details
        )


class InvalidChoiceException(FieldValidationException):
    """Exception for invalid choices from a predefined list."""
    
    def __init__(
        self,
        field: str,
        value: Any,
        valid_choices: List[Any]
    ):
        message = f"Invalid choice. Valid options: {', '.join(str(c) for c in valid_choices)}"
        
        details = {
            "valid_choices": valid_choices,
            "choice_count": len(valid_choices)
        }
        
        super().__init__(
            field=field,
            message=message,
            value=value,
            details=details
        )


class DateValidationException(FieldValidationException):
    """Exception for date validation errors."""
    
    def __init__(
        self,
        field: str,
        value: str,
        message: str = "Invalid date format"
    ):
        super().__init__(
            field=field,
            message=message,
            value=value
        )


class DateRangeException(ValidationException):
    """Exception for invalid date ranges."""
    
    def __init__(
        self,
        start_field: str,
        end_field: str,
        start_date: str,
        end_date: str,
        message: str = "Start date must be before end date"
    ):
        details = {
            "start_field": start_field,
            "end_field": end_field,
            "start_date": start_date,
            "end_date": end_date
        }
        
        super().__init__(
            message=message,
            details=details
        )


class FileValidationException(ValidationException):
    """Exception for file validation errors."""
    
    def __init__(
        self,
        message: str,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        content_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        if filename:
            details["filename"] = filename
        if file_size:
            details["file_size"] = file_size
        if content_type:
            details["content_type"] = content_type
        
        super().__init__(
            message=message,
            error_code="FILE_VALIDATION_ERROR",
            details=details
        )


class FileSizeException(FileValidationException):
    """Exception for file size violations."""
    
    def __init__(
        self,
        filename: str,
        file_size: int,
        max_size: int
    ):
        message = f"File size {file_size} bytes exceeds maximum allowed size {max_size} bytes"
        
        super().__init__(
            message=message,
            filename=filename,
            file_size=file_size,
            details={"max_size": max_size}
        )


class FileTypeException(FileValidationException):
    """Exception for invalid file types."""
    
    def __init__(
        self,
        filename: str,
        file_extension: str,
        allowed_extensions: List[str]
    ):
        message = f"File type '{file_extension}' not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        super().__init__(
            message=message,
            filename=filename,
            details={
                "file_extension": file_extension,
                "allowed_extensions": allowed_extensions
            }
        )


class ContentValidationException(ValidationException):
    """Exception for content validation errors."""
    
    def __init__(
        self,
        content_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        details["content_type"] = content_type
        
        super().__init__(
            message=f"{content_type} validation failed: {message}",
            error_code="CONTENT_VALIDATION_ERROR",
            details=details
        )


class ProfanityException(ContentValidationException):
    """Exception for content containing profanity."""
    
    def __init__(
        self,
        field: str = "content",
        message: str = "Content contains inappropriate language"
    ):
        super().__init__(
            content_type="text",
            message=message,
            details={"field": field}
        )


class SpamException(ContentValidationException):
    """Exception for content identified as spam."""
    
    def __init__(
        self,
        field: str = "content",
        message: str = "Content identified as spam",
        confidence: Optional[float] = None
    ):
        details = {"field": field}
        if confidence:
            details["spam_confidence"] = confidence
        
        super().__init__(
            content_type="text",
            message=message,
            details=details
        )


class DuplicateValueException(ValidationException):
    """Exception for duplicate values where uniqueness is required."""
    
    def __init__(
        self,
        field: str,
        value: Any,
        message: Optional[str] = None
    ):
        if message is None:
            message = f"Value '{value}' already exists"
        
        super().__init__(
            message=message,
            field=field,
            value=value,
            error_code="DUPLICATE_VALUE"
        )


class CrossFieldValidationException(ValidationException):
    """Exception for validation errors involving multiple fields."""
    
    def __init__(
        self,
        fields: List[str],
        message: str,
        values: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        details["fields"] = fields
        
        if values:
            details["values"] = values
        
        super().__init__(
            message=message,
            error_code="CROSS_FIELD_VALIDATION",
            details=details
        )