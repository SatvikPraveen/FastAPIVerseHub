# File: app/middleware/cors_middleware.py

from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application."""
    
    # Parse CORS origins from settings
    allowed_origins = settings.cors_origins_list
    
    # Add CORS middleware with comprehensive configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.cors_methods_list,
        allow_headers=["*"] if settings.CORS_HEADERS == "*" else settings.CORS_HEADERS.split(","),
        expose_headers=[
            "X-Process-Time",
            "X-Request-ID", 
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ],
        max_age=3600  # Cache preflight requests for 1 hour
    )


class CustomCORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware with advanced features."""
    
    def __init__(
        self,
        app,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = False,
        expose_headers: List[str] = None,
        max_age: int = 3600,
        vary_header: bool = True,
        allow_origin_regex: Optional[str] = None
    ):
        super().__init__(app)
        
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers or []
        self.max_age = max_age
        self.vary_header = vary_header
        self.allow_origin_regex = allow_origin_regex
        
        # Compile regex if provided
        self.origin_regex = None
        if allow_origin_regex:
            import re
            self.origin_regex = re.compile(allow_origin_regex)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Handle CORS for incoming requests."""
        
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            
            # Set CORS headers for preflight
            self._set_cors_headers(response, origin, is_preflight=True)
            
            return response
        
        # Process actual request
        response = await call_next(request)
        
        # Set CORS headers for actual response
        self._set_cors_headers(response, origin, is_preflight=False)
        
        return response
    
    def _set_cors_headers(self, response: Response, origin: Optional[str], is_preflight: bool):
        """Set appropriate CORS headers on response."""
        
        # Determine if origin is allowed
        allowed_origin = self._get_allowed_origin(origin)
        
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # Set Vary header to indicate that the response varies by Origin
        if self.vary_header and origin:
            existing_vary = response.headers.get("Vary", "")
            if "Origin" not in existing_vary:
                new_vary = "Origin" if not existing_vary else f"{existing_vary}, Origin"
                response.headers["Vary"] = new_vary
        
        # For preflight requests, set additional headers
        if is_preflight:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            
            if self.allow_headers and self.allow_headers != ["*"]:
                response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            else:
                # Echo back the requested headers
                requested_headers = response.headers.get("Access-Control-Request-Headers")
                if requested_headers:
                    response.headers["Access-Control-Allow-Headers"] = requested_headers
            
            response.headers["Access-Control-Max-Age"] = str(self.max_age)
        
        # Set exposed headers for actual responses
        if not is_preflight and self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
    
    def _get_allowed_origin(self, origin: Optional[str]) -> Optional[str]:
        """Determine if origin is allowed and return the appropriate value."""
        
        if not origin:
            return None
        
        # Check wildcard
        if "*" in self.allow_origins:
            # If credentials are allowed, we can't use wildcard
            if self.allow_credentials:
                # Check if origin is in explicit list or matches regex
                if origin in self.allow_origins or self._matches_origin_regex(origin):
                    return origin
                return None
            else:
                return "*"
        
        # Check explicit origins
        if origin in self.allow_origins:
            return origin
        
        # Check regex pattern
        if self._matches_origin_regex(origin):
            return origin
        
        return None
    
    def _matches_origin_regex(self, origin: str) -> bool:
        """Check if origin matches the regex pattern."""
        if not self.origin_regex:
            return False
        
        try:
            return bool(self.origin_regex.match(origin))
        except Exception:
            return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""
    
    def __init__(
        self,
        app,
        add_security_headers: bool = True,
        content_security_policy: Optional[str] = None,
        referrer_policy: str = "strict-origin-when-cross-origin",
        x_content_type_options: bool = True,
        x_frame_options: str = "DENY",
        x_xss_protection: bool = True,
        strict_transport_security: Optional[str] = None
    ):
        super().__init__(app)
        
        self.add_security_headers = add_security_headers
        self.content_security_policy = content_security_policy
        self.referrer_policy = referrer_policy
        self.x_content_type_options = x_content_type_options
        self.x_frame_options = x_frame_options
        self.x_xss_protection = x_xss_protection
        self.strict_transport_security = strict_transport_security
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        
        response = await call_next(request)
        
        if not self.add_security_headers:
            return response
        
        # Content Security Policy
        if self.content_security_policy:
            response.headers["Content-Security-Policy"] = self.content_security_policy
        
        # Referrer Policy
        if self.referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy
        
        # X-Content-Type-Options
        if self.x_content_type_options:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options
        if self.x_frame_options:
            response.headers["X-Frame-Options"] = self.x_frame_options
        
        # X-XSS-Protection
        if self.x_xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict-Transport-Security (HTTPS only)
        if self.strict_transport_security and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self.strict_transport_security
        
        # Additional security headers
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        
        return response


def create_development_cors_config() -> dict:
    """Create CORS configuration for development environment."""
    return {
        "allow_origins": [
            "http://localhost:3000",
            "http://localhost:3001", 
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080"
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": [
            "X-Process-Time",
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
    }


def create_production_cors_config() -> dict:
    """Create CORS configuration for production environment."""
    return {
        "allow_origins": settings.cors_origins_list,
        "allow_credentials": settings.CORS_CREDENTIALS,
        "allow_methods": settings.cors_methods_list,
        "allow_headers": [
            "Accept",
            "Accept-Language", 
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Requested-With"
        ],
        "expose_headers": [
            "X-Process-Time",
            "X-Request-ID",
            "X-RateLimit-Limit", 
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Content-Range",
            "X-Content-Range"
        ]
    }


def get_cors_config() -> dict:
    """Get appropriate CORS configuration based on environment."""
    if settings.ENVIRONMENT == "development":
        return create_development_cors_config()
    else:
        return create_production_cors_config()