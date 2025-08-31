#!/usr/bin/env python3
"""
File Location: scripts/benchmark_apis.py

Performance benchmarking script for FastAPIVerseHub APIs.
Tests various endpoints under different load conditions.
"""

import asyncio
import aiohttp
import time
import statistics
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse

@dataclass
class BenchmarkResult:
    endpoint: str
    method: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    median_response_time: float
    p95_response_time: float
    requests_per_second: float
    error_rate: float
    errors: List[str]

class APIBenchmark:
    def __init__(self, base_url: str = "http://localhost:8000", auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.results: List[BenchmarkResult] = []
    
    async def authenticate(self) -> str:
        """Get authentication token"""
        print("Authenticating...")
        
        # Try to login with default test user
        login_data = {
            "username": "admin@example.com",
            "password": "admin123"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/auth/token",
                data=login_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    token = data.get("access_token")
                    print("✓ Authentication successful")
                    return token
                else:
                    print("✗ Authentication failed - some tests will be skipped")
                    return None
    
    async def make_request(self, session: aiohttp.ClientSession, method: str, 
                          endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a single API request and measure response time"""
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop('headers', {})
        
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        start_time = time.time()
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                # Try to read response body
                try:
                    body = await response.text()
                except:
                    body = ""
                
                return {
                    'success': response.status < 400,
                    'status_code': response.status,
                    'response_time': response_time,
                    'body_size': len(body),
                    'error': None if response.status < 400 else f"HTTP {response.status}"
                }
        
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            return {
                'success': False,
                'status_code': 0,
                'response_time': response_time,
                'body_size': 0,
                'error': str(e)
            }
    
    async def benchmark_endpoint(self, method: str, endpoint: str, 
                                concurrent_requests: int = 10, 
                                total_requests: int = 100,
                                **request_kwargs) -> BenchmarkResult:
        """Benchmark a single endpoint"""
        print(f"\nBenchmarking {method} {endpoint}")
        print(f"Concurrent requests: {concurrent_requests}, Total requests: {total_requests}")
        
        connector = aiohttp.TCPConnector(limit=concurrent_requests * 2)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(concurrent_requests)
            
            async def bounded_request():
                async with semaphore:
                    return await self.make_request(session, method, endpoint, **request_kwargs)
            
            # Start timing
            start_time = time.time()
            
            # Execute all requests
            tasks = [bounded_request() for _ in range(total_requests)]
            results = await asyncio.gather(*tasks)
            
            # End timing
            end_time = time.time()
            total_time = end_time - start_time
        
        # Process results
        successful_requests = sum(1 for r in results if r['success'])
        failed_requests = total_requests - successful_requests
        
        response_times = [r['response_time'] for r in results]
        errors = [r['error'] for r in results if r['error']]
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        median_response_time = statistics.median(response_times) if response_times else 0
        
        # Calculate 95th percentile
        if response_times:
            response_times.sort()
            p95_index = int(0.95 * len(response_times))
            p95_response_time = response_times[p95_index]
        else:
            p95_response_time = 0
        
        requests_per_second = total_requests / total_time if total_time > 0 else 0
        error_rate = (failed_requests / total_requests) * 100
        
        result = BenchmarkResult(
            endpoint=endpoint,
            method=method,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            median_response_time=median_response_time,
            p95_response_time=p95_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            errors=errors[:10]  # Only keep first 10 errors
        )
        
        self.results.append(result)
        self._print_result(result)
        return result
    
    def _print_result(self, result: BenchmarkResult):
        """Print benchmark result"""
        print(f"  Total requests: {result.total_requests}")
        print(f"  Successful: {result.successful_requests}")
        print(f"  Failed: {result.failed_requests}")
        print(f"  Error rate: {result.error_rate:.2f}%")
        print(f"  Avg response time: {result.avg_response_time*1000:.2f}ms")
        print(f"  Min response time: {result.min_response_time*1000:.2f}ms")
        print(f"  Max response time: {result.max_response_time*1000:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time*1000:.2f}ms")
        print(f"  Requests/sec: {result.requests_per_second:.2f}")
    
    async def run_benchmarks(self, concurrent_requests: int = 10, total_requests: int = 100):
        """Run all benchmark tests"""
        print("FastAPIVerseHub API Benchmark")
        print("=" * 40)
        
        # Authenticate if possible
        if not self.auth_token:
            self.auth_token = await self.authenticate()
        
        # Test endpoints
        endpoints = [
            # Public endpoints
            ("GET", "/health"),
            ("GET", "/docs"),
            ("POST", "/api/v1/auth/token", {
                "data": {"username": "admin@example.com", "password": "admin123"}
            }),
            
            # Protected endpoints (if authenticated)
            ("GET", "/api/v1/users/me"),
            ("GET", "/api/v1/users/"),
            ("GET", "/api/v1/courses/"),
            
            # CRUD operations
            ("POST", "/api/v1/courses/", {
                "json": {
                    "title": f"Benchmark Test Course {datetime.now().isoformat()}",
                    "description": "Test course for benchmarking",
                    "category": "Programming",
                    "difficulty": "beginner",
                    "estimated_duration": 60
                }
            }),
        ]
        
        for method, endpoint, *kwargs in endpoints:
            request_kwargs = kwargs[0] if kwargs else {}
            
            # Skip protected endpoints if not authenticated
            if endpoint.startswith("/api/v1/") and endpoint not in ["/api/v1/auth/token"] and not self.auth_token:
                print(f"Skipping {method} {endpoint} (not authenticated)")
                continue
            
            try:
                await self.benchmark_endpoint(
                    method, endpoint, 
                    concurrent_requests=concurrent_requests,
                    total_requests=total_requests,
                    **request_kwargs
                )
            except Exception as e:
                print(f"Error benchmarking {method} {endpoint}: {e}")
        
        self._print_summary()
        return self.results
    
    def _print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        
        if not self.results:
            print("No benchmark results available")
            return
        
        # Calculate overall statistics
        total_requests = sum(r.total_requests for r in self.results)
        total_successful = sum(r.successful_requests for r in self.results)
        total_failed = sum(r.failed_requests for r in self.results)
        overall_error_rate = (total_failed / total_requests) * 100 if total_requests > 0 else 0
        
        avg_rps = statistics.mean([r.requests_per_second for r in self.results])
        avg_response_time = statistics.mean([r.avg_response_time for r in self.results])
        
        print(f"Total requests: {total_requests}")
        print(f"Successful requests: {total_successful}")
        print(f"Failed requests: {total_failed}")
        print(f"Overall error rate: {overall_error_rate:.2f}%")
        print(f"Average RPS: {avg_rps:.2f}")
        print(f"Average response time: {avg_response_time*1000:.2f}ms")
        
        # Top performers
        print(f"\nFastest endpoints:")
        fastest = sorted(self.results, key=lambda x: x.avg_response_time)[:3]
        for i, result in enumerate(fastest, 1):
            print(f"  {i}. {result.method} {result.endpoint}: {result.avg_response_time*1000:.2f}ms")
        
        # Slowest endpoints
        print(f"\nSlowest endpoints:")
        slowest = sorted(self.results, key=lambda x: x.avg_response_time, reverse=True)[:3]
        for i, result in enumerate(slowest, 1):
            print(f"  {i}. {result.method} {result.endpoint}: {result.avg_response_time*1000:.2f}ms")
        
        # Error summary
        error_results = [r for r in self.results if r.failed_requests > 0]
        if error_results:
            print(f"\nEndpoints with errors:")
            for result in error_results:
                print(f"  {result.method} {result.endpoint}: {result.error_rate:.2f}% error rate")
    
    def export_results(self, filename: str = "benchmark_results.json"):
        """Export results to JSON file"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "results": [
                {
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "total_requests": r.total_requests,
                    "successful_requests": r.successful_requests,
                    "failed_requests": r.failed_requests,
                    "avg_response_time": r.avg_response_time,
                    "min_response_time": r.min_response_time,
                    "max_response_time": r.max_response_time,
                    "median_response_time": r.median_response_time,
                    "p95_response_time": r.p95_response_time,
                    "requests_per_second": r.requests_per_second,
                    "error_rate": r.error_rate,
                    "errors": r.errors
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults exported to {filename}")

async def main():
    parser = argparse.ArgumentParser(description="FastAPIVerseHub API Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--total", type=int, default=100, help="Total requests per endpoint")
    parser.add_argument("--token", help="Authentication token")
    parser.add_argument("--export", help="Export results to JSON file")
    
    args = parser.parse_args()
    
    benchmark = APIBenchmark(base_url=args.url, auth_token=args.token)
    
    try:
        await benchmark.run_benchmarks(
            concurrent_requests=args.concurrent,
            total_requests=args.total
        )
        
        if args.export:
            benchmark.export_results(args.export)
    
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
    except Exception as e:
        print(f"Benchmark failed: {e}")

if __name__ == "__main__":
    # Install required packages if not present
    try:
        import aiohttp
    except ImportError:
        print("Installing required packages...")
        import os
        os.system("pip install aiohttp")
    
    asyncio.run(main())