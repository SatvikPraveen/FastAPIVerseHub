# File: app/schemas/common.py

from datetime import datetime
from typing import Generic, List, Optional, TypeVar, Any, Dict

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar('T')


class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response schema."""
    items: List[T]
    total: int
    skip: int = 0
    limit: int = 100
    has_next: bool = False
    has_prev: bool = False
    page: Optional[int] = None
    total_pages: Optional[int] = None
    
    class Config:
        arbitrary_types_allowed = True


class SuccessResponse(BaseModel):
    """Standard success response schema."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    success: bool = False
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheck(BaseModel):
    """Health check response schema."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    environment: str
    database: str = "connected"
    redis: str = "connected"
    uptime_seconds: Optional[int] = None


class MetaData(BaseModel):
    """Metadata for API responses."""
    api_version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    execution_time_ms: Optional[float] = None


class SearchParams(BaseModel):
    """Common search parameters schema."""
    q: Optional[str] = Field(None, description="Search query")
    sort_by: Optional[str] = Field("created_at", description="Sort field")
    order: str = Field("desc", regex="^(asc|desc)$", description="Sort order")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


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
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    def __post_init__(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")


class SortOption(BaseModel):
    """Sort option schema."""
    field: str
    direction: str = Field("asc", regex="^(asc|desc)$")
    
    class Config:
        schema_extra = {
            "example": {
                "field": "created_at",
                "direction": "desc"
            }
        }


class FilterOption(BaseModel):
    """Filter option schema."""
    field: str
    operator: str = Field("eq", regex="^(eq|ne|gt|gte|lt|lte|in|nin|contains|startswith|endswith)$")
    value: Any
    
    class Config:
        schema_extra = {
            "example": {
                "field": "status",
                "operator": "eq",
                "value": "active"
            }
        }


class BulkOperation(BaseModel):
    """Bulk operation schema."""
    action: str
    ids: List[int] = Field(..., min_items=1, max_items=1000)
    data: Optional[Dict[str, Any]] = None


class BulkOperationResult(BaseModel):
    """Bulk operation result schema."""
    total_requested: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = []
    results: Optional[List[Dict[str, Any]]] = None


class FileUploadResponse(BaseModel):
    """File upload response schema."""
    id: Optional[int] = None
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    upload_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Analytics(BaseModel):
    """Generic analytics schema."""
    total_count: int = 0
    growth_rate: Optional[float] = None
    period_comparison: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = {}
    charts_data: Optional[List[Dict[str, Any]]] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(BaseModel):
    """Notification schema."""
    id: Optional[int] = None
    title: str
    message: str
    type: str = Field("info", regex="^(info|success|warning|error)$")
    read: bool = False
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActivityLog(BaseModel):
    """Activity log schema."""
    id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    description: str
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CacheInfo(BaseModel):
    """Cache information schema."""
    key: str
    value: Optional[Any] = None
    ttl_seconds: Optional[int] = None
    created_at: Optional[datetime] = None
    accessed_at: Optional[datetime] = None
    hit_count: int = 0


class RateLimitInfo(BaseModel):
    """Rate limit information schema."""
    limit: int
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None


class APIUsage(BaseModel):
    """API usage statistics schema."""
    endpoint: str
    method: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    last_accessed: Optional[datetime] = None


class SystemStatus(BaseModel):
    """System status schema."""
    component: str
    status: str = Field("operational", regex="^(operational|degraded|down|maintenance)$")
    message: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    uptime_percentage: Optional[float] = None


class ValidationError(BaseModel):
    """Validation error detail schema."""
    field: str
    message: str
    invalid_value: Optional[Any] = None


class BatchRequest(BaseModel):
    """Batch request schema."""
    requests: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100)
    stop_on_error: bool = False


class BatchResponse(BaseModel):
    """Batch response schema."""
    results: List[Dict[str, Any]]
    total_requests: int
    successful: int
    failed: int
    execution_time_ms: float