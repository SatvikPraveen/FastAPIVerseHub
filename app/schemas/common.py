# File: app/schemas/common.py

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""

    items: list[T]
    total: int
    skip: int = 0
    limit: int = 100
    has_next: bool = False
    has_prev: bool = False
    page: int | None = None
    total_pages: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SuccessResponse(BaseModel):
    """Standard success response schema."""

    success: bool = True
    message: str
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    success: bool = False
    error_code: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheck(BaseModel):
    """Health check response schema."""

    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    environment: str
    database: str = "connected"
    redis: str = "connected"
    uptime_seconds: int | None = None


class MetaData(BaseModel):
    """Metadata for API responses."""

    api_version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = None
    execution_time_ms: float | None = None


class SearchParams(BaseModel):
    """Common search parameters schema."""

    q: str | None = Field(None, description="Search query")
    sort_by: str | None = Field("created_at", description="Sort field")
    order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")
    filters: dict[str, Any] | None = Field(None, description="Additional filters")


class PaginationParams(BaseModel):
    """Common pagination parameters schema."""

    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(20, ge=1, le=100, description="Number of items to return")

    @property
    def offset(self) -> int:
        """Get offset value."""
        return self.skip

    @property
    def page_size(self) -> int:
        """Get page size."""
        return self.limit

    def get_page_number(self) -> int:
        """Calculate current page number."""
        return (self.skip // self.limit) + 1


class DateRangeFilter(BaseModel):
    """Date range filter schema."""

    start_date: datetime | None = None
    end_date: datetime | None = None

    @model_validator(mode="after")
    def check_range(self) -> "DateRangeFilter":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        return self


class SortOption(BaseModel):
    """Sort option schema."""

    field: str
    direction: str = Field("asc", pattern="^(asc|desc)$")

    model_config = ConfigDict(
        json_schema_extra={"example": {"field": "created_at", "direction": "desc"}}
    )


class FilterOption(BaseModel):
    """Filter option schema."""

    field: str
    operator: str = Field(
        "eq", pattern="^(eq|ne|gt|gte|lt|lte|in|nin|contains|startswith|endswith)$"
    )
    value: Any

    model_config = ConfigDict(
        json_schema_extra={"example": {"field": "status", "operator": "eq", "value": "active"}}
    )


class BulkOperation(BaseModel):
    """Bulk operation schema."""

    action: str
    ids: list[int] = Field(..., min_length=1, max_length=1000)
    data: dict[str, Any] | None = None


class BulkOperationResult(BaseModel):
    """Bulk operation result schema."""

    total_requested: int
    successful: int
    failed: int
    errors: list[dict[str, Any]] = []
    results: list[dict[str, Any]] | None = None


class FileUploadResponse(BaseModel):
    """File upload response schema."""

    id: int | None = None
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    file_path: str | None = None
    download_url: str | None = None
    upload_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Analytics(BaseModel):
    """Generic analytics schema."""

    total_count: int = 0
    growth_rate: float | None = None
    period_comparison: dict[str, Any] | None = None
    metrics: dict[str, Any] = {}
    charts_data: list[dict[str, Any]] | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(BaseModel):
    """Notification schema."""

    id: int | None = None
    title: str
    message: str
    type: str = Field("info", pattern="^(info|success|warning|error)$")
    read: bool = False
    data: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActivityLog(BaseModel):
    """Activity log schema."""

    id: int | None = None
    user_id: int | None = None
    action: str
    resource_type: str
    resource_id: int | None = None
    description: str
    metadata: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CacheInfo(BaseModel):
    """Cache information schema."""

    key: str
    value: Any | None = None
    ttl_seconds: int | None = None
    created_at: datetime | None = None
    accessed_at: datetime | None = None
    hit_count: int = 0


class RateLimitInfo(BaseModel):
    """Rate limit information schema."""

    limit: int
    remaining: int
    reset_at: datetime
    retry_after: int | None = None


class APIUsage(BaseModel):
    """API usage statistics schema."""

    endpoint: str
    method: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    last_accessed: datetime | None = None


class SystemStatus(BaseModel):
    """System status schema."""

    component: str
    status: str = Field("operational", pattern="^(operational|degraded|down|maintenance)$")
    message: str | None = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    uptime_percentage: float | None = None


class ValidationError(BaseModel):
    """Validation error detail schema."""

    field: str
    message: str
    invalid_value: Any | None = None


class BatchRequest(BaseModel):
    """Batch request schema."""

    requests: list[dict[str, Any]] = Field(..., min_length=1, max_length=100)
    stop_on_error: bool = False


class BatchResponse(BaseModel):
    """Batch response schema."""

    results: list[dict[str, Any]]
    total_requests: int
    successful: int
    failed: int
    execution_time_ms: float
