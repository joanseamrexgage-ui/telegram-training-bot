"""
Performance tests for TimeoutMiddleware.

Tests:
- Latency benchmarks for fast handlers
- Latency benchmarks for slow handlers
- Throughput under load
- Memory usage monitoring
- Timeout accuracy benchmarks
- Concurrent request handling performance
"""

import pytest
import asyncio
import time
import psutil
import os
from unittest.mock import MagicMock
from typing import List, Dict, Any

from middlewares.timeout import TimeoutMiddleware


class TestTimeoutMiddlewarePerformance:
    """Performance test suite for TimeoutMiddleware"""

    # ==================== LATENCY BENCHMARK TESTS ====================

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_fast_handler_latency_benchmark(self):
        """Benchmark latency for fast handlers (sub-millisecond expected)."""
        timeout_middleware = TimeoutMiddleware(timeout=30)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.001)  # 1ms handler
            return "fast_result"
        
        # Warm-up
        for _ in range(10):
            await timeout_middleware(fast_handler, MagicMock(), {})
        
        # Benchmark
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter()
            await timeout_middleware(fast_handler, MagicMock(), {})
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        max_latency = max(latencies)
        
        # Performance assertions
        assert avg_latency < 10.0  # Average < 10ms
        assert p95_latency < 25.0  # 95th percentile < 25ms
        assert max_latency < 50.0  # Max < 50ms
        
        print(f"\nFast Handler Latency Results:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  P99: {p99_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_slow_handler_timeout_accuracy_benchmark(self):
        """Benchmark timeout accuracy for slow handlers."""
        timeout_middleware = TimeoutMiddleware(timeout=1.0)
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Much longer than timeout
            return "should_not_reach"
        
        # Benchmark timeout accuracy
        timeout_durations = []
        for _ in range(50):
            start_time = time.perf_counter()
            await timeout_middleware(slow_handler, MagicMock(), {})
            end_time = time.perf_counter()
            
            timeout_duration = end_time - start_time
            timeout_durations.append(timeout_duration)
        
        # Calculate timeout accuracy
        avg_timeout_duration = sum(timeout_durations) / len(timeout_durations)
        timeout_variance = sum((d - avg_timeout_duration) ** 2 for d in timeout_durations) / len(timeout_durations)
        timeout_std_dev = timeout_variance ** 0.5
        
        # Timeout accuracy assertions
        assert avg_timeout_duration >= 0.95  # Should be at least 95% of timeout
        assert avg_timeout_duration <= 1.05  # Should be at most 105% of timeout
        assert timeout_std_dev < 0.1  # Low variance
        
        print(f"\nTimeout Accuracy Results:")
        print(f"  Target timeout: 1.0s")
        print(f"  Average duration: {avg_timeout_duration:.3f}s")
        print(f"  Standard deviation: {timeout_std_dev:.3f}s")
        print(f"  Accuracy: {(avg_timeout_duration/1.0)*100:.1f}%")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_middleware_overhead_benchmark(self):
        """Benchmark middleware overhead compared to direct handler execution."""
        timeout_middleware = TimeoutMiddleware(timeout=30)
        
        async def benchmark_handler(event, data):
            await asyncio.sleep(0.001)  # 1ms of work
            return "result"
        
        # Benchmark direct execution
        direct_times = []
        for _ in range(100):
            start_time = time.perf_counter()
            await benchmark_handler(MagicMock(), {})
            end_time = time.perf_counter()
            direct_times.append(end_time - start_time)
        
        # Benchmark with middleware
        middleware_times = []
        for _ in range(100):
            start_time = time.perf_counter()
            await timeout_middleware(benchmark_handler, MagicMock(), {})
            end_time = time.perf_counter()
            middleware_times.append(end_time - start_time)
        
        # Calculate overhead
        direct_avg = sum(direct_times) / len(direct_times)
        middleware_avg = sum(middleware_times) / len(middleware_times)
        overhead_us = (middleware_avg - direct_avg) * 1000000  # Microseconds
        
        # Overhead assertions
        assert overhead_us < 1000  # Less than 1ms overhead
        overhead_percent = ((middleware_avg - direct_avg) / direct_avg) * 100
        assert overhead_percent < 50  # Less than 50% overhead
        
        print(f"\nMiddleware Overhead Results:")
        print(f"  Direct execution: {direct_avg*1000:.2f}ms")
        print(f"  With middleware: {middleware_avg*1000:.2f}ms")
        print(f"  Overhead: {overhead_us:.0f}μs ({overhead_percent:.1f}%)")

    # ==================== THROUGHPUT TESTS ====================

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_throughput_single_handler(self):
        """Test throughput with single handler type."""
        timeout_middleware = TimeoutMiddleware(timeout=10)
        
        async def throughput_handler(event, data):
            await asyncio.sleep(0.01)  # 10ms per request
            return "processed"
        
        # Measure throughput
        start_time = time.time()
        processed_count = 0
        
        async def process_requests():
            nonlocal processed_count
            for _ in range(50):
                result = await timeout_middleware(throughput_handler, MagicMock(), {})
                if result:
                    processed_count += 1
        
        await process_requests()
        end_time = time.time()
        
        duration = end_time - start_time
        throughput = processed_count / duration
        
        # Throughput assertions
        assert throughput > 20  # At least 20 requests/second
        assert throughput < 200  # Reasonable upper bound
        
        print(f"\nThroughput Results:")
        print(f"  Processed: {processed_count} requests")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Throughput: {throughput:.1f} req/s")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_throughput_concurrent_requests(self):
        """Test throughput with concurrent requests."""
        timeout_middleware = TimeoutMiddleware(timeout=10)
        
        async def concurrent_handler(event, data):
            user_id = event.from_user.id if event.from_user else 0
            # Simulate user-specific processing time
            await asyncio.sleep(0.001 * (user_id % 10 + 1))
            return f"user_{user_id}"
        
        # Test concurrent throughput
        concurrent_users = 20
        requests_per_user = 10
        
        start_time = time.time()
        
        async def process_user_batch(user_start_id):
            tasks = []
            for i in range(requests_per_user):
                event = MagicMock()
                event.from_user = MagicMock()
                event.from_user.id = user_start_id + i
                task = timeout_middleware(concurrent_handler, event, {})
                tasks.append(task)
            
            return await asyncio.gather(*tasks)
        
        # Process all user batches concurrently
        batch_tasks = []
        for batch_start in range(0, concurrent_users, 5):  # 5 batches of 4 users
            batch_tasks.append(process_user_batch(batch_start))
        
        results = await asyncio.gather(*batch_tasks)
        end_time = time.time()
        
        total_requests = concurrent_users * requests_per_user
        duration = end_time - start_time
        throughput = total_requests / duration
        
        # Concurrent throughput assertions
        assert throughput > 50  # Higher throughput with concurrency
        assert len([r for batch in results for r in batch if r]) == total_requests
        
        print(f"\nConcurrent Throughput Results:")
        print(f"  Users: {concurrent_users}")
        print(f"  Requests per user: {requests_per_user}")
        print(f"  Total requests: {total_requests}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Concurrent throughput: {throughput:.1f} req/s")

    # ==================== MEMORY USAGE TESTS ====================

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """Monitor memory usage during high-load operations."""
        timeout_middleware = TimeoutMiddleware(timeout=5)
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        async def memory_test_handler(event, data):
            await asyncio.sleep(0.1)
            return "memory_test"
        
        # Process many requests to detect memory leaks
        for batch in range(10):
            # Process batch of requests
            tasks = []
            for _ in range(20):
                event = MagicMock()
                event.from_user = MagicMock()
                event.from_user.id = batch * 20 + _ 
                task = timeout_middleware(memory_test_handler, event, {})
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Check memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory assertions (should not grow significantly)
            assert memory_increase < 50  # Less than 50MB increase
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"\nMemory Usage Results:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Total increase: {total_increase:.1f} MB")
        print(f"  Requests processed: 200")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_cleanup_after_stress_test(self):
        """Test memory cleanup after stress testing."""
        timeout_middleware = TimeoutMiddleware(timeout=2)
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Stress test - many quick operations
        async def stress_handler(event, data):
            await asyncio.sleep(0.001)
            return "stress_result"
        
        # High volume of operations
        for _ in range(100):
            tasks = []
            for _ in range(10):
                event = MagicMock()
                event.from_user = MagicMock()
                event.from_user.id = _
                task = timeout_middleware(stress_handler, event, {})
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        # Force garbage collection
        import gc
        gc.collect()
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_after_gc = process.memory_info().rss / 1024 / 1024  # MB
        
        # Memory cleanup assertions
        memory_freed = peak_memory - memory_after_gc
        assert memory_freed > 0  # Some memory should be freed
        
        print(f"\nMemory Cleanup Results:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(f"  Peak: {peak_memory:.1f} MB")
        print(f"  After GC: {memory_after_gc:.1f} MB")
        print(f"  Memory freed: {memory_freed:.1f} MB")

    # ==================== CONCURRENT PERFORMANCE TESTS ====================

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_timeout_accuracy(self):
        """Test timeout accuracy under concurrent load."""
        timeout_middleware = TimeoutMiddleware(timeout=1.0)
        
        async def concurrent_slow_handler(event, data):
            # All handlers should timeout at approximately the same time
            await asyncio.sleep(5.0)
            return "should_not_reach"
        
        # Start all concurrent timeouts
        start_time = time.perf_counter()
        
        # 50 concurrent slow handlers
        tasks = []
        for i in range(50):
            event = MagicMock()
            event.from_user = MagicMock()
            event.from_user.id = 1000 + i
            task = timeout_middleware(concurrent_slow_handler, event, {})
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()
        
        total_duration = end_time - start_time
        
        # Concurrent timeout assertions
        assert all(r is None or isinstance(r, asyncio.TimeoutError) for r in results)
        assert timeout_middleware.stats["timeouts"] == 50
        
        # All timeouts should complete within reasonable time of each other
        assert total_duration < 2.0  # All should timeout within 2x the timeout duration
        
        print(f"\nConcurrent Timeout Results:")
        print(f"  Concurrent handlers: 50")
        print(f"  Total duration: {total_duration:.3f}s")
        print(f"  Timeouts recorded: {timeout_middleware.stats['timeouts']}")
        print(f"  All handlers timed out: {all(r is None for r in results)}")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self):
        """Test performance with mixed workload (fast, medium, slow handlers)."""
        timeout_middleware = TimeoutMiddleware(timeout=2.0)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.01)  # 10ms
            return "fast"
        
        async def medium_handler(event, data):
            await asyncio.sleep(0.5)  # 500ms
            return "medium"
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "slow"
        
        async def error_handler(event, data):
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        # Mixed workload
        workload = [
            (fast_handler, 30),    # 30 fast requests
            (medium_handler, 10),  # 10 medium requests
            (slow_handler, 5),     # 5 slow requests (will timeout)
            (error_handler, 5)     # 5 error requests
        ]
        
        start_time = time.perf_counter()
        
        async def process_mixed_workload():
            all_tasks = []
            
            for handler, count in workload:
                for i in range(count):
                    event = MagicMock()
                    event.from_user = MagicMock()
                    event.from_user.id = hash(f"{handler.__name__}_{i}") % 100000
                    
                    task = timeout_middleware(handler, event, {})
                    all_tasks.append(task)
            
            # Process all tasks
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            return results
        
        results = await process_mixed_workload()
        end_time = time.perf_counter()
        
        # Analyze results
        fast_results = [r for r in results if r == "fast"]
        medium_results = [r for r in results if r == "medium"]
        timeout_results = [r for r in results if r is None]
        error_results = [r for r in results if isinstance(r, Exception)]
        
        total_duration = end_time - start_time
        
        # Mixed workload assertions
        assert len(fast_results) == 30
        assert len(medium_results) == 10
        assert len(timeout_results) == 5  # slow_handler requests
        assert len(error_results) == 5   # error_handler requests
        
        # Performance should be reasonable
        assert total_duration < 30.0  # Should complete within 30 seconds
        
        print(f"\nMixed Workload Results:")
        print(f"  Fast requests: {len(fast_results)}/30")
        print(f"  Medium requests: {len(medium_results)}/10")
        print(f"  Timeout requests: {len(timeout_results)}/5")
        print(f"  Error requests: {len(error_results)}/5")
        print(f"  Total duration: {total_duration:.2f}s")
        print(f"  Throughput: {len(results)/total_duration:.1f} req/s")

    # ==================== STATISTICS PERFORMANCE TESTS ====================

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_statistics_performance_impact(self):
        """Test that statistics tracking doesn't significantly impact performance."""
        timeout_middleware = TimeoutMiddleware(timeout=30)
        
        async def stats_test_handler(event, data):
            await asyncio.sleep(0.01)
            return "stats_test"
        
        # Benchmark with statistics tracking
        start_time = time.perf_counter()
        
        for _ in range(100):
            await timeout_middleware(stats_test_handler, MagicMock(), {})
        
        end_time = time.perf_counter()
        
        # Test statistics retrieval performance
        stats_start = time.perf_counter()
        for _ in range(1000):
            stats = timeout_middleware.get_stats()
        stats_end = time.perf_counter()
        
        processing_time = end_time - start_time
        stats_retrieval_time = stats_end - stats_start
        
        # Statistics performance assertions
        assert stats_retrieval_time < 0.1  # 1000 stats retrievals should be < 100ms
        assert processing_time > 1.0  # Should take some time due to 100 * 10ms handlers
        
        print(f"\nStatistics Performance Results:")
        print(f"  100 handler executions: {processing_time:.3f}s")
        print(f"  1000 stats retrievals: {stats_retrieval_time:.3f}s")
        print(f"  Avg per stat retrieval: {stats_retrieval_time/1000*1000:.3f}ms")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self):
        """Regression test to detect performance degradation over time."""
        timeout_middleware = TimeoutMiddleware(timeout=10)
        
        async def regression_test_handler(event, data):
            await asyncio.sleep(0.01)
            return "regression_test"
        
        # Test performance over multiple iterations
        performance_samples = []
        
        for iteration in range(5):
            start_time = time.perf_counter()
            
            # Process batch of requests
            for _ in range(20):
                await timeout_middleware(regression_test_handler, MagicMock(), {})
            
            end_time = time.perf_counter()
            batch_duration = end_time - start_time
            performance_samples.append(batch_duration)
            
            # Small delay between iterations
            await asyncio.sleep(0.1)
        
        # Performance regression assertions
        first_sample = performance_samples[0]
        last_sample = performance_samples[-1]
        
        # Should not have significant performance degradation
        performance_degradation = (last_sample - first_sample) / first_sample
        assert performance_degradation < 0.2  # Less than 20% degradation
        
        print(f"\nPerformance Regression Results:")
        print(f"  First iteration: {first_sample:.3f}s")
        print(f"  Last iteration: {last_sample:.3f}s")
        print(f"  Degradation: {performance_degradation*100:.1f}%")
        print(f"  All samples: {[f'{s:.3f}s' for s in performance_samples]}")
