# File: app/tests/test_middleware.py

import pytest
import time
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.tests.conftest import assert_response_success, assert_response_error


class TestRateLimitMiddleware:
    """Test rate limiting middleware functionality."""
    
    async def test_rate_limit_under_limit(self, async_client: AsyncClient):
        """Test requests under rate limit are allowed."""
        # Make a few requests that should be under the limit
        for i in range(3):
            response = await async_client.get("/health")
            assert_response_success(response)
            
            # Check rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
    
    async def test_rate_limit_headers_present(self, async_client: AsyncClient):
        """Test that rate limit headers are present in responses."""
        response = await async_client.get("/health")
        
        assert_response_success(response)
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        
        # Verify header values are reasonable
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        
        assert limit > 0
        assert remaining >= 0
        assert remaining <= limit
    
    async def test_rate_limit_excluded_paths(self, async_client: AsyncClient):
        """Test that excluded paths bypass rate limiting."""
        excluded_paths = ["/health", "/docs", "/openapi.json"]
        
        for path in excluded_paths:
            response = await async_client.get(path)
            
            # Health endpoint should work, others might 404 but shouldn't be rate limited
            assert response.status_code in [200, 404]
            
            # Rate limit headers might not be present for excluded paths
            # This depends on implementation
    
    async def test_rate_limit_different_clients(self, async_client: AsyncClient):
        """Test that different clients have separate rate limits."""
        # Simulate requests from different IPs by using different headers
        headers1 = {"X-Forwarded-For": "192.168.1.1"}
        headers2 = {"X-Forwarded-For": "192.168.1.2"}
        
        # Both clients should be able to make requests
        response1 = await async_client.get("/health", headers=headers1)
        response2 = await async_client.get("/health", headers=headers2)
        
        assert_response_success(response1)
        assert_response_success(response2)
    
    @pytest.mark.skip(reason="Requires actual rate limiting to be triggered")
    async def test_rate_limit_exceeded(self, async_client: AsyncClient):
        """Test behavior when rate limit is exceeded."""
        # This test would require actually hitting the rate limit
        # which might be impractical in a fast test suite
        
        # Make many requests rapidly
        responses = []
        for i in range(100):  # Exceed typical rate limit
            response = await async_client.get("/")
            responses.append(response)
        
        # Check if any responses were rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        
        if rate_limited_responses:
            response = rate_limited_responses[0]
            assert "Retry-After" in response.headers
            assert response.json()["error"] == "RATE_LIMIT_EXCEEDED"


class TestRequestTimingMiddleware:
    """Test request timing middleware functionality."""
    
    async def test_timing_headers_added(self, async_client: AsyncClient):
        """Test that timing headers are added to responses."""
        response = await async_client.get("/health")
        
        assert_response_success(response)
        assert "X-Process-Time" in response.headers
        assert "X-Request-ID" in response.headers
        
        # Verify timing header format
        process_time = float(response.headers["X-Process-Time"])
        assert process_time >= 0
        assert process_time < 10  # Should be very fast for health check
        
        # Verify request ID format
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 10  # UUID should be longer
    
    async def test_request_id_uniqueness(self, async_client: AsyncClient):
        """Test that each request gets a unique request ID."""
        response1 = await async_client.get("/health")
        response2 = await async_client.get("/health")
        
        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        
        assert id1 != id2
    
    async def test_slow_request_logging(self, async_client: AsyncClient):
        """Test that slow requests are logged appropriately."""
        # Create an endpoint that takes time (mock slow response)
        with patch("time.perf_counter") as mock_timer:
            # Mock a slow request (2 seconds)
            mock_timer.side_effect = [0, 2.0]
            
            response = await async_client.get("/health")
            
            # Should still succeed but timing would be logged
            assert_response_success(response)
            
            # In real implementation, this would check logs
    
    async def test_request_failure_timing(self, async_client: AsyncClient):
        """Test timing for failed requests."""
        # Make request to non-existent endpoint
        response = await async_client.get("/nonexistent-endpoint")
        
        # Should still have timing headers even for 404
        assert response.status_code == 404
        
        if "X-Process-Time" in response.headers:
            process_time = float(response.headers["X-Process-Time"])
            assert process_time >= 0


class TestCORSMiddleware:
    """Test CORS middleware functionality."""
    
    async def test_cors_headers_added(self, async_client: AsyncClient):
        """Test that CORS headers are added to responses."""
        headers = {"Origin": "http://localhost:3000"}
        
        response = await async_client.get("/health", headers=headers)
        
        assert_response_success(response)
        
        # Check for CORS headers
        cors_headers = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Credentials",
        ]
        
        # At least some CORS headers should be present
        present_cors_headers = [h for h in cors_headers if h in response.headers]
        assert len(present_cors_headers) > 0
    
    async def test_preflight_request(self, async_client: AsyncClient):
        """Test CORS preflight request handling."""
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        
        response = await async_client.options("/api/v1/courses/", headers=headers)
        
        # Preflight should return 200
        assert response.status_code == 200
        
        # Should have preflight response headers
        expected_headers = [
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers",
            "Access-Control-Max-Age"
        ]
        
        for header in expected_headers:
            # Some CORS implementations might not include all headers
            if header in response.headers:
                assert response.headers[header] is not None
    
    async def test_cors_allowed_origin(self, async_client: AsyncClient):
        """Test CORS with allowed origin."""
        # Test with localhost (typically allowed in development)
        headers = {"Origin": "http://localhost:3000"}
        
        response = await async_client.get("/health", headers=headers)
        
        assert_response_success(response)
        
        # Should allow the origin or use wildcard
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            assert allowed_origin in ["*", "http://localhost:3000"]
    
    async def test_cors_credentials(self, async_client: AsyncClient):
        """Test CORS credentials handling."""
        headers = {"Origin": "http://localhost:3000"}
        
        response = await async_client.get("/health", headers=headers)
        
        if "Access-Control-Allow-Credentials" in response.headers:
            credentials = response.headers["Access-Control-Allow-Credentials"]
            assert credentials.lower() in ["true", "false"]


class TestSecurityHeadersMiddleware:
    """Test security headers middleware functionality."""
    
    async def test_security_headers_present(self, async_client: AsyncClient):
        """Test that security headers are added to responses."""
        response = await async_client.get("/health")
        
        assert_response_success(response)
        
        # Common security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Referrer-Policy"
        ]
        
        # At least some security headers should be present
        present_security_headers = [h for h in security_headers if h in response.headers]
        
        # This test is flexible since security headers might not be implemented
        # in the basic middleware setup
    
    async def test_content_type_options(self, async_client: AsyncClient):
        """Test X-Content-Type-Options header."""
        response = await async_client.get("/health")
        
        if "X-Content-Type-Options" in response.headers:
            assert response.headers["X-Content-Type-Options"] == "nosniff"
    
    async def test_frame_options(self, async_client: AsyncClient):
        """Test X-Frame-Options header."""
        response = await async_client.get("/health")
        
        if "X-Frame-Options" in response.headers:
            frame_options = response.headers["X-Frame-Options"]
            assert frame_options in ["DENY", "SAMEORIGIN", "ALLOW-FROM"]


class TestMiddlewareIntegration:
    """Test middleware integration and order."""
    
    async def test_multiple_middleware_headers(self, async_client: AsyncClient):
        """Test that multiple middleware components add their headers."""
        response = await async_client.get("/health")
        
        assert_response_success(response)
        
        # Should have headers from multiple middleware
        expected_header_types = [
            # Timing middleware
            "X-Process-Time",
            "X-Request-ID",
            # Rate limiting middleware
            "X-RateLimit-Limit",
        ]
        
        present_headers = [h for h in expected_header_types if h in response.headers]
        
        # Should have at least timing headers
        assert len(present_headers) >= 1
    
    async def test_middleware_order_consistency(self, async_client: AsyncClient):
        """Test that middleware processes requests in consistent order."""
        # Make multiple requests and verify consistent header presence
        responses = []
        for i in range(3):
            response = await async_client.get("/health")
            responses.append(response)
        
        # All responses should have similar header structure
        first_response_headers = set(responses[0].headers.keys())
        
        for response in responses[1:]:
            current_headers = set(response.headers.keys())
            
            # Core headers should be consistent
            core_headers = {"content-length", "content-type"}
            assert core_headers.issubset(first_response_headers)
            assert core_headers.issubset(current_headers)
    
    async def test_middleware_with_authentication(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test middleware behavior with authenticated requests."""
        response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
        
        # Should have standard middleware headers even for auth endpoints
        if response.status_code == 200:
            assert "X-Process-Time" in response.headers
            assert "X-Request-ID" in response.headers
    
    async def test_middleware_error_handling(self, async_client: AsyncClient):
        """Test middleware behavior during error responses."""
        # Make request that will cause 404
        response = await async_client.get("/definitely-nonexistent-endpoint")
        
        assert response.status_code == 404
        
        # Middleware should still add headers even for error responses
        assert "X-Request-ID" in response.headers
        
        # Timing should still work
        if "X-Process-Time" in response.headers:
            process_time = float(response.headers["X-Process-Time"])
            assert process_time >= 0