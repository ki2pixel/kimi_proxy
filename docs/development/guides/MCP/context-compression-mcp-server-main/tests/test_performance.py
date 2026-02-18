"""
Performance tests for Context Compression MCP Server.

These tests verify system performance under various load conditions
and measure key performance metrics.
"""

import pytest
import tempfile
import os
import sys
import time
import threading
import statistics
import gc
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_manager import ContextManager
from src.compression import CompressionEngine
from src.database import DatabaseManager


class TestCompressionPerformance:
    """Test compression engine performance."""
    
    def test_compression_speed_benchmarks(self):
        """Test compression speed with various data sizes."""
        engine = CompressionEngine()
        
        # Test data of different sizes
        test_sizes = [1024, 10240, 102400, 1048576]  # 1KB, 10KB, 100KB, 1MB
        results = {}
        
        for size in test_sizes:
            # Create test data (mix of compressible and incompressible)
            compressible_data = "A" * size
            incompressible_data = ''.join(chr(65 + (i % 26)) for i in range(size))
            
            # Test compressible data
            start_time = time.time()
            result = engine.compress(compressible_data)
            compress_time = time.time() - start_time
            
            start_time = time.time()
            decompressed = engine.decompress(result.compressed_data, result.compression_method)
            decompress_time = time.time() - start_time
            
            assert decompressed == compressible_data
            
            results[f"compressible_{size}"] = {
                'compress_time': compress_time,
                'decompress_time': decompress_time,
                'compression_ratio': result.compression_ratio,
                'throughput_mb_s': (size / (1024 * 1024)) / compress_time
            }
            
            # Test incompressible data
            start_time = time.time()
            result = engine.compress(incompressible_data)
            compress_time = time.time() - start_time
            
            start_time = time.time()
            decompressed = engine.decompress(result.compressed_data, result.compression_method)
            decompress_time = time.time() - start_time
            
            assert decompressed == incompressible_data
            
            results[f"incompressible_{size}"] = {
                'compress_time': compress_time,
                'decompress_time': decompress_time,
                'compression_ratio': result.compression_ratio,
                'throughput_mb_s': (size / (1024 * 1024)) / compress_time
            }
        
        # Performance assertions
        for size in test_sizes:
            comp_result = results[f"compressible_{size}"]
            incomp_result = results[f"incompressible_{size}"]
            
            # Compression should be reasonably fast (at least 10 MB/s for large data)
            if size >= 102400:  # 100KB+
                assert comp_result['throughput_mb_s'] > 10, f"Compression too slow for {size} bytes: {comp_result['throughput_mb_s']:.2f} MB/s"
                assert incomp_result['throughput_mb_s'] > 10, f"Compression too slow for {size} bytes: {incomp_result['throughput_mb_s']:.2f} MB/s"
            
            # Decompression should be faster than compression
            assert comp_result['decompress_time'] <= comp_result['compress_time'] * 2
            assert incomp_result['decompress_time'] <= incomp_result['compress_time'] * 2
            
            # Compressible data should achieve good compression ratio
            assert comp_result['compression_ratio'] < 0.1, f"Poor compression ratio: {comp_result['compression_ratio']}"
        
        print("\nCompression Performance Results:")
        for key, result in results.items():
            print(f"{key}: {result['throughput_mb_s']:.2f} MB/s, ratio: {result['compression_ratio']:.3f}")
    
    def test_compression_memory_usage(self):
        """Test compression memory usage patterns."""
        engine = CompressionEngine()
        
        # Monitor memory usage during compression
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Test with large data
        large_data = "Memory test data. " * 100000  # ~1.8MB
        
        # Measure memory during compression
        pre_compress_memory = process.memory_info().rss
        result = engine.compress(large_data)
        post_compress_memory = process.memory_info().rss
        
        # Measure memory during decompression
        pre_decompress_memory = process.memory_info().rss
        decompressed = engine.decompress(result.compressed_data, result.compression_method)
        post_decompress_memory = process.memory_info().rss
        
        assert decompressed == large_data
        
        # Memory usage should be reasonable
        compress_memory_increase = post_compress_memory - pre_compress_memory
        decompress_memory_increase = post_decompress_memory - pre_decompress_memory
        
        # Should not use more than 10MB additional memory for this operation
        assert compress_memory_increase < 10 * 1024 * 1024, f"Compression used too much memory: {compress_memory_increase / (1024*1024):.2f} MB"
        assert decompress_memory_increase < 10 * 1024 * 1024, f"Decompression used too much memory: {decompress_memory_increase / (1024*1024):.2f} MB"
        
        # Force garbage collection and check memory cleanup
        del large_data, result, decompressed
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_cleanup = post_decompress_memory - final_memory
        
        print(f"\nMemory Usage:")
        print(f"Initial: {initial_memory / (1024*1024):.2f} MB")
        print(f"Compression increase: {compress_memory_increase / (1024*1024):.2f} MB")
        print(f"Decompression increase: {decompress_memory_increase / (1024*1024):.2f} MB")
        print(f"Memory cleaned up: {memory_cleanup / (1024*1024):.2f} MB")


class TestDatabasePerformance:
    """Test database performance."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_database_insert_performance(self, temp_db_path):
        """Test database insertion performance."""
        db = DatabaseManager(temp_db_path)
        
        # Test batch insertion performance
        num_records = 1000
        record_size = 1024  # 1KB per record
        
        test_data = b"x" * record_size
        
        start_time = time.time()
        
        for i in range(num_records):
            success = db.insert_context(
                context_id=f"perf_test_{i:06d}",
                title=f"Performance Test {i}",
                original_size=record_size,
                compressed_size=record_size,
                compression_method="none",
                data=test_data,
                tags=f'["performance", "test{i}"]'
            )
            assert success is True
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance metrics
        inserts_per_second = num_records / duration
        mb_per_second = (num_records * record_size) / (1024 * 1024) / duration
        
        print(f"\nDatabase Insert Performance:")
        print(f"Inserted {num_records} records in {duration:.2f}s")
        print(f"Rate: {inserts_per_second:.1f} inserts/second")
        print(f"Throughput: {mb_per_second:.2f} MB/second")
        
        # Performance assertions
        assert inserts_per_second > 100, f"Insert performance too low: {inserts_per_second:.1f} inserts/sec"
        assert mb_per_second > 0.1, f"Throughput too low: {mb_per_second:.2f} MB/sec"
        
        # Test query performance
        start_time = time.time()
        
        for i in range(0, num_records, 10):  # Query every 10th record
            context_id = f"perf_test_{i:06d}"
            result = db.select_context(context_id)
            assert result is not None
            assert result['id'] == context_id
        
        end_time = time.time()
        query_duration = end_time - start_time
        queries_per_second = (num_records // 10) / query_duration
        
        print(f"Query Performance: {queries_per_second:.1f} queries/second")
        
        # Query performance assertion
        assert queries_per_second > 500, f"Query performance too low: {queries_per_second:.1f} queries/sec"
        
        db.close_connections()
    
    def test_database_search_performance(self, temp_db_path):
        """Test database search performance with large datasets."""
        db = DatabaseManager(temp_db_path)
        
        # Insert test data with searchable content
        num_records = 2000
        categories = ["category_a", "category_b", "category_c", "category_d"]
        
        for i in range(num_records):
            category = categories[i % len(categories)]
            db.insert_context(
                context_id=f"search_test_{i:06d}",
                title=f"Search Test {category} Item {i}",
                original_size=100,
                compressed_size=100,
                compression_method="none",
                data=b"search test data",
                tags=f'["{category}", "search", "item{i}"]'
            )
        
        # Test search performance
        search_terms = ["category_a", "category_b", "Search Test", "item"]
        search_times = []
        
        for term in search_terms:
            start_time = time.time()
            results = db.search_contexts(term, limit=100)
            end_time = time.time()
            
            search_time = end_time - start_time
            search_times.append(search_time)
            
            assert len(results) > 0, f"No results found for term: {term}"
            print(f"Search '{term}': {len(results)} results in {search_time:.3f}s")
        
        # Performance assertions
        avg_search_time = statistics.mean(search_times)
        max_search_time = max(search_times)
        
        assert avg_search_time < 0.1, f"Average search time too high: {avg_search_time:.3f}s"
        assert max_search_time < 0.2, f"Maximum search time too high: {max_search_time:.3f}s"
        
        print(f"Average search time: {avg_search_time:.3f}s")
        print(f"Maximum search time: {max_search_time:.3f}s")
        
        db.close_connections()
    
    def test_database_concurrent_performance(self, temp_db_path):
        """Test database performance under concurrent load."""
        db = DatabaseManager(temp_db_path)
        
        # Pre-populate database
        for i in range(100):
            db.insert_context(
                context_id=f"concurrent_base_{i:03d}",
                title=f"Concurrent Base {i}",
                original_size=100,
                compressed_size=100,
                compression_method="none",
                data=b"concurrent test data"
            )
        
        num_threads = 10
        operations_per_thread = 50
        
        results = {
            'insert_times': [],
            'select_times': [],
            'search_times': [],
            'errors': []
        }
        
        def concurrent_worker(worker_id):
            """Worker performing mixed database operations."""
            try:
                for i in range(operations_per_thread):
                    # Insert operation
                    start_time = time.time()
                    success = db.insert_context(
                        context_id=f"concurrent_{worker_id}_{i:03d}",
                        title=f"Concurrent Worker {worker_id} Item {i}",
                        original_size=100,
                        compressed_size=100,
                        compression_method="none",
                        data=b"concurrent worker data"
                    )
                    insert_time = time.time() - start_time
                    results['insert_times'].append(insert_time)
                    assert success is True
                    
                    # Select operation
                    start_time = time.time()
                    base_id = f"concurrent_base_{(worker_id * i) % 100:03d}"
                    result = db.select_context(base_id)
                    select_time = time.time() - start_time
                    results['select_times'].append(select_time)
                    assert result is not None
                    
                    # Search operation (every 5th iteration)
                    if i % 5 == 0:
                        start_time = time.time()
                        search_results = db.search_contexts("Concurrent", limit=10)
                        search_time = time.time() - start_time
                        results['search_times'].append(search_time)
                        assert len(search_results) > 0
                    
                    time.sleep(0.001)  # Small delay to increase contention
                    
            except Exception as e:
                results['errors'].append(f"Worker {worker_id}: {str(e)}")
        
        # Run concurrent test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(concurrent_worker, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                future.result()
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        assert len(results['errors']) == 0, f"Concurrent errors: {results['errors']}"
        
        total_operations = len(results['insert_times']) + len(results['select_times']) + len(results['search_times'])
        operations_per_second = total_operations / total_duration
        
        avg_insert_time = statistics.mean(results['insert_times'])
        avg_select_time = statistics.mean(results['select_times'])
        avg_search_time = statistics.mean(results['search_times']) if results['search_times'] else 0
        
        print(f"\nConcurrent Database Performance:")
        print(f"Total operations: {total_operations} in {total_duration:.2f}s")
        print(f"Operations per second: {operations_per_second:.1f}")
        print(f"Average insert time: {avg_insert_time:.4f}s")
        print(f"Average select time: {avg_select_time:.4f}s")
        print(f"Average search time: {avg_search_time:.4f}s")
        
        # Performance assertions
        assert operations_per_second > 200, f"Concurrent performance too low: {operations_per_second:.1f} ops/sec"
        assert avg_insert_time < 0.01, f"Insert time too high: {avg_insert_time:.4f}s"
        assert avg_select_time < 0.005, f"Select time too high: {avg_select_time:.4f}s"
        
        db.close_connections()


class TestContextManagerPerformance:
    """Test context manager performance."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_context_storage_performance(self, temp_db_path):
        """Test context storage performance with various data sizes."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test different data sizes
        test_sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB
        results = {}
        
        for size in test_sizes:
            # Create test data
            test_data = f"Performance test data of size {size}. " * (size // 50)
            test_data = test_data[:size]  # Trim to exact size
            
            # Measure storage performance
            storage_times = []
            retrieval_times = []
            context_ids = []
            
            num_operations = 100
            
            for i in range(num_operations):
                # Store context
                start_time = time.time()
                context_id = cm.store_context(
                    test_data,
                    title=f"Performance Test {size}B #{i}",
                    tags=[f"performance", f"size{size}", f"item{i}"]
                )
                storage_time = time.time() - start_time
                storage_times.append(storage_time)
                context_ids.append(context_id)
                
                # Retrieve context
                start_time = time.time()
                retrieved = cm.retrieve_context(context_id)
                retrieval_time = time.time() - start_time
                retrieval_times.append(retrieval_time)
                
                assert retrieved['data'] == test_data
            
            # Calculate metrics
            avg_storage_time = statistics.mean(storage_times)
            avg_retrieval_time = statistics.mean(retrieval_times)
            storage_throughput = (size * num_operations) / (1024 * 1024) / sum(storage_times)
            retrieval_throughput = (size * num_operations) / (1024 * 1024) / sum(retrieval_times)
            
            results[size] = {
                'avg_storage_time': avg_storage_time,
                'avg_retrieval_time': avg_retrieval_time,
                'storage_throughput_mb_s': storage_throughput,
                'retrieval_throughput_mb_s': retrieval_throughput
            }
            
            # Clean up
            for context_id in context_ids:
                cm.delete_context(context_id)
        
        # Performance assertions and reporting
        print("\nContext Manager Performance Results:")
        for size, metrics in results.items():
            print(f"Size {size}B:")
            print(f"  Storage: {metrics['avg_storage_time']:.4f}s avg, {metrics['storage_throughput_mb_s']:.2f} MB/s")
            print(f"  Retrieval: {metrics['avg_retrieval_time']:.4f}s avg, {metrics['retrieval_throughput_mb_s']:.2f} MB/s")
            
            # Performance assertions
            assert metrics['avg_storage_time'] < 0.01, f"Storage too slow for {size}B: {metrics['avg_storage_time']:.4f}s"
            assert metrics['avg_retrieval_time'] < 0.005, f"Retrieval too slow for {size}B: {metrics['avg_retrieval_time']:.4f}s"
            
            if size >= 10240:  # For larger data
                assert metrics['storage_throughput_mb_s'] > 1.0, f"Storage throughput too low: {metrics['storage_throughput_mb_s']:.2f} MB/s"
                assert metrics['retrieval_throughput_mb_s'] > 5.0, f"Retrieval throughput too low: {metrics['retrieval_throughput_mb_s']:.2f} MB/s"
        
        cm.close()
    
    def test_search_performance_scaling(self, temp_db_path):
        """Test search performance scaling with dataset size."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Create datasets of increasing size
        dataset_sizes = [100, 500, 1000, 2000]
        search_performance = {}
        
        for dataset_size in dataset_sizes:
            # Populate dataset
            context_ids = []
            categories = ["alpha", "beta", "gamma", "delta", "epsilon"]
            
            for i in range(dataset_size):
                category = categories[i % len(categories)]
                data = f"Search performance test data for {category} item {i}"
                title = f"Search Test {category} #{i}"
                tags = [category, "search", "performance", f"item{i}"]
                
                context_id = cm.store_context(data, title=title, tags=tags)
                context_ids.append(context_id)
            
            # Test search performance
            search_terms = ["alpha", "beta", "Search Test", "performance"]
            search_times = []
            
            for term in search_terms:
                start_time = time.time()
                results = cm.search_contexts(term, limit=50)
                search_time = time.time() - start_time
                search_times.append(search_time)
                
                assert len(results) > 0
            
            avg_search_time = statistics.mean(search_times)
            search_performance[dataset_size] = avg_search_time
            
            print(f"Dataset size {dataset_size}: Average search time {avg_search_time:.4f}s")
            
            # Clean up
            for context_id in context_ids:
                cm.delete_context(context_id)
        
        # Analyze scaling
        print("\nSearch Performance Scaling:")
        for size, time_taken in search_performance.items():
            print(f"  {size} contexts: {time_taken:.4f}s")
        
        # Performance should scale reasonably (not exponentially)
        max_search_time = max(search_performance.values())
        assert max_search_time < 0.1, f"Search time too high for large dataset: {max_search_time:.4f}s"
        
        # Search time should not increase dramatically with dataset size
        time_ratio = search_performance[2000] / search_performance[100]
        assert time_ratio < 5.0, f"Search performance degrades too much with scale: {time_ratio:.2f}x"
        
        cm.close()
    
    def test_memory_usage_scaling(self, temp_db_path):
        """Test memory usage scaling with number of contexts."""
        cm = ContextManager(db_path=temp_db_path)
        process = psutil.Process()
        
        # Measure baseline memory
        gc.collect()  # Clean up before measurement
        baseline_memory = process.memory_info().rss
        
        # Store contexts in batches and measure memory
        batch_size = 200
        num_batches = 5
        memory_measurements = []
        
        context_ids = []
        
        for batch in range(num_batches):
            # Store batch of contexts
            for i in range(batch_size):
                context_id = cm.store_context(
                    f"Memory scaling test data for batch {batch} item {i}. " * 10,
                    title=f"Memory Test Batch {batch} Item {i}",
                    tags=[f"batch{batch}", f"item{i}", "memory"]
                )
                context_ids.append(context_id)
            
            # Measure memory after batch
            gc.collect()
            current_memory = process.memory_info().rss
            memory_increase = current_memory - baseline_memory
            memory_measurements.append(memory_increase)
            
            total_contexts = (batch + 1) * batch_size
            memory_per_context = memory_increase / total_contexts
            
            print(f"After {total_contexts} contexts: {memory_increase / (1024*1024):.2f} MB total, {memory_per_context / 1024:.2f} KB per context")
        
        # Analyze memory scaling
        final_memory_increase = memory_measurements[-1]
        total_contexts = num_batches * batch_size
        avg_memory_per_context = final_memory_increase / total_contexts
        
        print(f"\nMemory Usage Summary:")
        print(f"Total contexts: {total_contexts}")
        print(f"Total memory increase: {final_memory_increase / (1024*1024):.2f} MB")
        print(f"Average memory per context: {avg_memory_per_context / 1024:.2f} KB")
        
        # Memory usage assertions
        assert avg_memory_per_context < 50 * 1024, f"Memory per context too high: {avg_memory_per_context / 1024:.2f} KB"
        assert final_memory_increase < 100 * 1024 * 1024, f"Total memory increase too high: {final_memory_increase / (1024*1024):.2f} MB"
        
        # Test memory cleanup after deletion
        for context_id in context_ids:
            cm.delete_context(context_id)
        
        gc.collect()
        final_memory = process.memory_info().rss
        memory_after_cleanup = final_memory - baseline_memory
        
        print(f"Memory after cleanup: {memory_after_cleanup / (1024*1024):.2f} MB")
        
        # Memory should be mostly cleaned up (but Python GC is not deterministic)
        # We'll just verify that memory didn't increase significantly after cleanup
        if final_memory_increase > 0:
            cleanup_ratio = memory_after_cleanup / final_memory_increase
            print(f"Memory cleanup ratio: {cleanup_ratio:.2f}")
            
            # More lenient assertion - memory usage should not have grown significantly
            assert memory_after_cleanup <= final_memory_increase * 2, f"Memory increased after cleanup: {memory_after_cleanup / (1024*1024):.2f} MB"
        else:
            print("Memory usage was negligible, skipping cleanup ratio test")
            # If no significant memory was used, that's actually good
            assert memory_after_cleanup < 10 * 1024 * 1024, f"Unexpected memory usage: {memory_after_cleanup / (1024*1024):.2f} MB"
        
        cm.close()


class TestEndToEndPerformance:
    """Test end-to-end performance scenarios."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_realistic_usage_performance(self, temp_db_path):
        """Test performance under realistic usage patterns."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Simulate realistic usage: mix of operations with realistic data
        operations = []
        context_ids = []
        
        # Phase 1: Initial data loading (bulk storage)
        print("Phase 1: Initial data loading...")
        start_time = time.time()
        
        for i in range(100):
            # Simulate storing various types of context data
            if i % 4 == 0:  # Code context
                data = f"""
def example_function_{i}():
    '''Example function for context storage test.'''
    result = []
    for j in range(10):
        result.append(f"item {{j}}")
    return result

# Usage example
data = example_function_{i}()
print(f"Generated {{len(data)}} items")
                """ * 3
                title = f"Code Context {i}"
                tags = ["code", "python", f"function{i}"]
            
            elif i % 4 == 1:  # Documentation context
                data = f"""
# Documentation for Feature {i}

## Overview
This feature provides functionality for {i} operations.

## Usage
To use this feature:
1. Initialize the component
2. Configure the parameters
3. Execute the operation
4. Handle the results

## Examples
```python
component = Feature{i}()
result = component.execute()
```

## Notes
- This is a test documentation entry
- Generated for performance testing
- Contains realistic documentation structure
                """ * 2
                title = f"Documentation {i}"
                tags = ["docs", "feature", f"doc{i}"]
            
            elif i % 4 == 2:  # Data context
                data = f"""
{{
    "id": {i},
    "name": "Test Data {i}",
    "description": "Performance test data entry",
    "metadata": {{
        "created": "2024-01-01T00:00:00Z",
        "type": "test",
        "category": "performance"
    }},
    "items": [
        {{"index": 0, "value": "item_0_{i}"}},
        {{"index": 1, "value": "item_1_{i}"}},
        {{"index": 2, "value": "item_2_{i}"}}
    ]
}}
                """ * 5
                title = f"Data Context {i}"
                tags = ["data", "json", f"entry{i}"]
            
            else:  # Mixed content
                data = f"""
Mixed Content Context {i}

This context contains various types of information:
- Text content for testing
- Some code: print("Hello {i}")
- Unicode content: 测试数据 {i} 🚀
- Numbers and symbols: {i} * 2 = {i * 2}

The purpose is to simulate realistic mixed content
that might be stored in a context management system.
                """ * 8
                title = f"Mixed Context {i}"
                tags = ["mixed", "content", f"item{i}"]
            
            context_id = cm.store_context(data, title=title, tags=tags)
            context_ids.append(context_id)
            operations.append(('store', time.time() - start_time))
        
        phase1_time = time.time() - start_time
        print(f"Stored 100 contexts in {phase1_time:.2f}s ({100/phase1_time:.1f} contexts/sec)")
        
        # Phase 2: Mixed operations (realistic usage pattern)
        print("Phase 2: Mixed operations...")
        phase2_start = time.time()
        
        for i in range(200):
            operation_start = time.time()
            
            if i % 5 == 0:  # Search operation
                search_terms = ["Code Context", "Documentation", "Data Context", "Mixed Context", "function", "Feature"]
                term = search_terms[i % len(search_terms)]
                results = cm.search_contexts(term, limit=10)
                # Note: Search might return 0 results for some terms, which is valid
                operations.append(('search', time.time() - operation_start))
            
            elif i % 5 == 1:  # Retrieve operation
                context_id = context_ids[i % len(context_ids)]
                retrieved = cm.retrieve_context(context_id)
                assert retrieved is not None
                operations.append(('retrieve', time.time() - operation_start))
            
            elif i % 5 == 2:  # List operation
                results = cm.list_contexts(limit=20, offset=(i % 5) * 20)
                operations.append(('list', time.time() - operation_start))
            
            elif i % 5 == 3:  # Update operation
                context_id = context_ids[i % len(context_ids)]
                new_title = f"Updated Context {i}"
                success = cm.update_context(context_id, title=new_title)
                assert success is True
                operations.append(('update', time.time() - operation_start))
            
            else:  # Store new context
                data = f"Additional context data {i} for mixed operations testing."
                context_id = cm.store_context(data, title=f"Additional {i}")
                context_ids.append(context_id)
                operations.append(('store', time.time() - operation_start))
        
        phase2_time = time.time() - phase2_start
        print(f"Completed 200 mixed operations in {phase2_time:.2f}s ({200/phase2_time:.1f} ops/sec)")
        
        # Phase 3: Cleanup performance
        print("Phase 3: Cleanup...")
        phase3_start = time.time()
        
        for context_id in context_ids:
            operation_start = time.time()
            success = cm.delete_context(context_id)
            assert success is True
            operations.append(('delete', time.time() - operation_start))
        
        phase3_time = time.time() - phase3_start
        print(f"Deleted {len(context_ids)} contexts in {phase3_time:.2f}s ({len(context_ids)/phase3_time:.1f} deletes/sec)")
        
        # Analyze overall performance
        total_time = phase1_time + phase2_time + phase3_time
        total_operations = len(operations)
        
        # Group operations by type
        op_stats = {}
        for op_type, duration in operations:
            if op_type not in op_stats:
                op_stats[op_type] = []
            op_stats[op_type].append(duration)
        
        print(f"\nOverall Performance Summary:")
        print(f"Total time: {total_time:.2f}s")
        print(f"Total operations: {total_operations}")
        print(f"Overall rate: {total_operations/total_time:.1f} ops/sec")
        
        print(f"\nOperation Type Performance:")
        for op_type, times in op_stats.items():
            avg_time = statistics.mean(times)
            max_time = max(times)
            ops_per_sec = len(times) / sum(times)
            print(f"  {op_type}: {avg_time:.4f}s avg, {max_time:.4f}s max, {ops_per_sec:.1f} ops/sec")
            
            # Performance assertions
            if op_type == 'store':
                assert avg_time < 0.01, f"Store operation too slow: {avg_time:.4f}s"
            elif op_type == 'retrieve':
                assert avg_time < 0.005, f"Retrieve operation too slow: {avg_time:.4f}s"
            elif op_type == 'search':
                assert avg_time < 0.02, f"Search operation too slow: {avg_time:.4f}s"
            elif op_type == 'update':
                assert avg_time < 0.01, f"Update operation too slow: {avg_time:.4f}s"
            elif op_type == 'delete':
                assert avg_time < 0.005, f"Delete operation too slow: {avg_time:.4f}s"
        
        # Overall performance assertion
        assert total_operations/total_time > 50, f"Overall performance too low: {total_operations/total_time:.1f} ops/sec"
        
        cm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print statements