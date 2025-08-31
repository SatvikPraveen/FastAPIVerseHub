# File: app/middleware/request_timer.py

import time
import uuid
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import request_logger

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to time requests and add correlation IDs."""
    
    def __init__(self, app, log_requests: bool = True, add_timing_header: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.add_timing_header = add_timing_header
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with timing and logging."""
        
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.request_id = correlation_id
        
        # Record start time
        start_time = time.perf_counter()
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Add correlation ID to request context
        request.state.correlation_id = correlation_id
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            end_time = time.perf_counter()
            duration = end_time - start_time
            
            # Add timing header
            if self.add_timing_header:
                response.headers["X-Process-Time"] = f"{duration:.4f}"
                response.headers["X-Request-ID"] = correlation_id
            
            # Log request
            if self.log_requests:
                user_id = getattr(request.state, "user_id", None)
                
                request_logger.log_request(
                    method=request.method,
                    url=str(request.url),
                    status_code=response.status_code,
                    duration=duration,
                    request_id=correlation_id,
                    user_id=user_id,
                    extra_data={
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                        "path": request.url.path,
                        "query_params": str(request.query_params),
                        "content_type": request.headers.get("content-type"),
                        "content_length": request.headers.get("content-length"),
                        "response_size": response.headers.get("content-length")
                    }
                )
            
            # Log slow requests
            if duration > 1.0:  # Log requests taking more than 1 second
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {duration:.4f}s",
                    extra={
                        "request_id": correlation_id,
                        "duration": duration,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code
                    }
                )
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            end_time = time.perf_counter()
            duration = end_time - start_time
            
            # Log failed request
            if self.log_requests:
                user_id = getattr(request.state, "user_id", None)
                
                request_logger.log_request(
                    method=request.method,
                    url=str(request.url),
                    status_code=500,
                    duration=duration,
                    request_id=correlation_id,
                    user_id=user_id,
                    extra_data={
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                        "error": str(e),
                        "exception_type": type(e).__name__
                    }
                )
            
            # Log error with context
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "request_id": correlation_id,
                    "duration": duration,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "exception_type": type(e).__name__
                },
                exc_info=True
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check forwarded headers first (for reverse proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"


class MetricsCollectionMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics for monitoring."""
    
    def __init__(self, app, collect_metrics: bool = True):
        super().__init__(app)
        self.collect_metrics = collect_metrics
        self.request_count = 0
        self.total_duration = 0.0
        self.status_counts = {}
        self.endpoint_metrics = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics during request processing."""
        
        if not self.collect_metrics:
            return await call_next(request)
        
        start_time = time.perf_counter()
        endpoint = f"{request.method} {request.url.path}"
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.perf_counter() - start_time
            
            # Update global metrics
            self.request_count += 1
            self.total_duration += duration
            
            # Update status code counts
            status_code = response.status_code
            self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1
            
            # Update endpoint metrics
            if endpoint not in self.endpoint_metrics:
                self.endpoint_metrics[endpoint] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "min_duration": float("inf"),
                    "max_duration": 0.0,
                    "status_codes": {}
                }
            
            endpoint_data = self.endpoint_metrics[endpoint]
            endpoint_data["count"] += 1
            endpoint_data["total_duration"] += duration
            endpoint_data["min_duration"] = min(endpoint_data["min_duration"], duration)
            endpoint_data["max_duration"] = max(endpoint_data["max_duration"], duration)
            endpoint_data["status_codes"][status_code] = endpoint_data["status_codes"].get(status_code, 0) + 1
            
            return response
            
        except Exception as e:
            # Update error metrics
            duration = time.perf_counter() - start_time
            self.request_count += 1
            self.total_duration += duration
            self.status_counts[500] = self.status_counts.get(500, 0) + 1
            
            raise
    
    def get_metrics(self) -> dict:
        """Get collected metrics."""
        avg_duration = self.total_duration / max(1, self.request_count)
        
        # Calculate endpoint averages
        endpoint_stats = {}
        for endpoint, data in self.endpoint_metrics.items():
            endpoint_stats[endpoint] = {
                "count": data["count"],
                "avg_duration": data["total_duration"] / max(1, data["count"]),
                "min_duration": data["min_duration"] if data["min_duration"] != float("inf") else 0,
                "max_duration": data["max_duration"],
                "status_codes": data["status_codes"]
            }
        
        return {
            "total_requests": self.request_count,
            "average_duration": avg_duration,
            "total_duration": self.total_duration,
            "status_codes": self.status_counts,
            "endpoints": endpoint_stats
        }
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        self.request_count = 0
        self.total_duration = 0.0
        self.status_counts = {}
        self.endpoint_metrics = {}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Advanced request logging middleware with filtering."""
    
    def __init__(
        self,
        app,
        log_requests: bool = True,
        log_responses: bool = False,
        exclude_paths: list = None,
        log_headers: bool = False,
        log_body: bool = False,
        max_body_size: int = 1024
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        self.log_headers = log_headers
        self.log_body = log_body
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log requests and responses with configurable detail level."""
        
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        correlation_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        if self.log_requests:
            await self._log_request(request, correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Log response
        if self.log_responses:
            await self._log_response(request, response, correlation_id)
        
        return response
    
    async def _log_request(self, request: Request, correlation_id: str):
        """Log incoming request details."""
        log_data = {
            "request_id": correlation_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request)
        }
        
        if self.log_headers:
            # Filter sensitive headers
            headers = dict(request.headers)
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                if header in headers:
                    headers[header] = "[REDACTED]"
            log_data["headers"] = headers
        
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    # Try to decode as text
                    try:
                        log_data["body"] = body.decode("utf-8")
                    except UnicodeDecodeError:
                        log_data["body"] = f"<binary data, {len(body)} bytes>"
                else:
                    log_data["body"] = f"<body too large, {len(body)} bytes>"
            except Exception:
                log_data["body"] = "<unable to read body>"
        
        logger.info(f"Incoming request: {request.method} {request.url.path}", extra=log_data)
    
    async def _log_response(self, request: Request, response: Response, correlation_id: str):
        """Log outgoing response details."""
        log_data = {
            "request_id": correlation_id,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "content_length": response.headers.get("content-length")
        }
        
        if self.log_headers:
            log_data["headers"] = dict(response.headers)
        
        logger.info(
            f"Outgoing response: {response.status_code} for {request.method} {request.url.path}",
            extra=log_data
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"


# Global metrics collector instance
metrics_collector = MetricsCollectionMiddleware(None)