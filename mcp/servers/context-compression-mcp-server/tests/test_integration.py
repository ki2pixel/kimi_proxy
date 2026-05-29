"""
Integration tests for Context Compression MCP Server.

These tests verify complete end-to-end workflows and integration
between all components of the system.
"""

import pytest
import tempfile
import os
import sys
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_manager import ContextManager
from src.compression import CompressionEngine
from src.database import DatabaseManager


class TestEndToEndIntegration:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_complete_context_lifecycle(self, temp_db_path):
        """Test complete lifecycle of context from creation to deletion."""
        cm = ContextManager(db_path=temp_db_path)
        
        # 1. Store context with all metadata
        original_data = "This is a comprehensive integration test for the context lifecycle."
        original_title = "Integration Test Context"
        original_tags = ["integration", "test", "lifecycle"]
        
        context_id = cm.store_context(original_data, title=original_title, tags=original_tags)
        assert context_id.startswith("ctx_")
        
        # 2. Retrieve and verify all data
        retrieved = cm.retrieve_context(context_id)
        assert retrieved['data'] == original_data
        assert retrieved['title'] == original_title
        assert retrieved['tags'] == original_tags
        assert 'metadata' in retrieved
        assert 'created_at' in retrieved['metadata']
        assert 'updated_at' in retrieved['metadata']
        
        # 3. Search for the context
        search_results = cm.search_contexts("integration")
        assert len(search_results) >= 1
        found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
        assert found_context is not None
        assert found_context['title'] == original_title
        
        # 4. List contexts and verify it appears
        list_results = cm.list_contexts()
        assert len(list_results) >= 1
        found_in_list = next((ctx for ctx in list_results if ctx['id'] == context_id), None)
        assert found_in_list is not None
        
        # 5. Update the context
        updated_data = "This is updated integration test data."
        updated_title = "Updated Integration Test"
        updated_tags = ["integration", "test", "updated"]
        
        success = cm.update_context(context_id, data=updated_data, title=updated_title, tags=updated_tags)
        assert success is True
        
        # 6. Verify update
        updated_retrieved = cm.retrieve_context(context_id)
        assert updated_retrieved['data'] == updated_data
        assert updated_retrieved['title'] == updated_title
        assert updated_retrieved['tags'] == updated_tags
        
        # 7. Get context summary
        summary = cm.get_context_summary(context_id)
        assert summary['id'] == context_id
        assert summary['title'] == updated_title
        assert summary['tags'] == updated_tags
        assert 'data' not in summary  # Summary should not include data
        
        # 8. Delete the context
        delete_success = cm.delete_context(context_id)
        assert delete_success is True
        
        # 9. Verify deletion
        with pytest.raises(RuntimeError, match="not found"):
            cm.retrieve_context(context_id)
        
        # 10. Verify it's gone from search and list
        search_after_delete = cm.search_contexts("integration")
        found_after_delete = next((ctx for ctx in search_after_delete if ctx['id'] == context_id), None)
        assert found_after_delete is None
        
        cm.close()
    
    def test_multi_context_workflow(self, temp_db_path):
        """Test workflows involving multiple contexts."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Create multiple related contexts
        contexts = []
        for i in range(10):
            data = f"Multi-context test data {i}. This context is part of a larger workflow test."
            title = f"Multi-Context Test {i}"
            tags = ["multi", "workflow", f"item{i}", f"group{i//3}"]
            
            context_id = cm.store_context(data, title=title, tags=tags)
            contexts.append({
                'id': context_id,
                'data': data,
                'title': title,
                'tags': tags
            })
        
        # Test batch retrieval
        for ctx in contexts:
            retrieved = cm.retrieve_context(ctx['id'])
            assert retrieved['data'] == ctx['data']
            assert retrieved['title'] == ctx['title']
            assert retrieved['tags'] == ctx['tags']
        
        # Test search across multiple contexts
        multi_search = cm.search_contexts("multi")
        assert len(multi_search) >= 10
        
        workflow_search = cm.search_contexts("workflow")
        assert len(workflow_search) >= 10
        
        # Test group-based search
        group0_search = cm.search_contexts("group0")
        assert len(group0_search) == 3  # Items 0, 1, 2
        
        group1_search = cm.search_contexts("group1")
        assert len(group1_search) == 3  # Items 3, 4, 5
        
        # Test pagination with multiple contexts
        page1 = cm.list_contexts(limit=5, offset=0)
        page2 = cm.list_contexts(limit=5, offset=5)
        
        assert len(page1) == 5
        assert len(page2) >= 5
        
        # Verify no overlap in pagination
        page1_ids = {ctx['id'] for ctx in page1}
        page2_ids = {ctx['id'] for ctx in page2}
        assert page1_ids.isdisjoint(page2_ids)
        
        # Test batch updates
        for i, ctx in enumerate(contexts[:5]):  # Update first 5
            new_title = f"Updated Multi-Context Test {i}"
            new_tags = ctx['tags'] + ["updated"]
            
            success = cm.update_context(ctx['id'], title=new_title, tags=new_tags)
            assert success is True
            
            # Verify update
            updated = cm.retrieve_context(ctx['id'])
            assert updated['title'] == new_title
            assert "updated" in updated['tags']
        
        # Test batch deletion
        for ctx in contexts:
            success = cm.delete_context(ctx['id'])
            assert success is True
        
        # Verify all deleted
        for ctx in contexts:
            with pytest.raises(RuntimeError, match="not found"):
                cm.retrieve_context(ctx['id'])
        
        cm.close()
    
    def test_cross_component_integration(self, temp_db_path):
        """Test integration between all components."""
        # Test with custom compression settings
        custom_compression = CompressionEngine(
            min_size_threshold=512,  # Lower threshold
            min_compression_ratio=0.9,  # More aggressive compression
            compression_level=9  # Maximum compression
        )
        
        cm = ContextManager(db_path=temp_db_path, compression_engine=custom_compression)
        
        # Test data that will trigger different compression behaviors
        test_cases = [
            {
                'name': 'small_data',
                'data': 'Small data that should not compress',
                'expected_method': 'none'
            },
            {
                'name': 'compressible_data',
                'data': 'A' * 1000,  # Highly compressible
                'expected_method': 'zlib'
            },
            {
                'name': 'unicode_data',
                'data': '你好世界 🌍 ' * 100,  # Unicode data
                'expected_method': 'zlib'  # Should compress
            }
        ]
        
        stored_contexts = []
        
        for case in test_cases:
            context_id = cm.store_context(
                case['data'],
                title=f"Cross-component test: {case['name']}",
                tags=[case['name'], 'cross-component']
            )
            
            # Verify storage
            retrieved = cm.retrieve_context(context_id)
            assert retrieved['data'] == case['data']
            assert retrieved['metadata']['compression_method'] == case['expected_method']
            
            stored_contexts.append({
                'id': context_id,
                'case': case
            })
        
        # Test search across different compression methods
        search_results = cm.search_contexts("cross-component")
        assert len(search_results) == 3
        
        # Verify each context has correct compression metadata
        for result in search_results:
            context_id = result['id']
            case_info = next(ctx for ctx in stored_contexts if ctx['id'] == context_id)
            
            assert result['metadata']['compression_method'] == case_info['case']['expected_method']
        
        # Test database-level verification
        db_info = cm.get_stats()
        assert db_info['total_contexts'] == 3
        assert db_info['compression_config']['min_size_threshold'] == 512
        assert db_info['compression_config']['compression_level'] == 9
        
        # Clean up
        for ctx in stored_contexts:
            cm.delete_context(ctx['id'])
        
        cm.close()
    
    def test_error_recovery_integration(self, temp_db_path):
        """Test system recovery from various error conditions."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Store some valid data first
        valid_id = cm.store_context("Valid data for recovery test", title="Valid Context")
        
        # Test recovery from compression errors
        original_compress = cm.compression.compress
        
        def failing_compress(data):
            if "fail_compress" in data:
                raise Exception("Simulated compression failure")
            return original_compress(data)
        
        cm.compression.compress = failing_compress
        
        # This should fail
        with pytest.raises(RuntimeError, match="Context storage failed"):
            cm.store_context("This should fail_compress", title="Failing Context")
        
        # Restore compression and verify system still works
        cm.compression.compress = original_compress
        
        # Should work again
        recovery_id = cm.store_context("Recovery test data", title="Recovery Context")
        retrieved = cm.retrieve_context(recovery_id)
        assert retrieved['data'] == "Recovery test data"
        
        # Verify original context still exists
        original_retrieved = cm.retrieve_context(valid_id)
        assert original_retrieved['data'] == "Valid data for recovery test"
        
        # Test recovery from database errors
        original_insert = cm.db.insert_context
        
        def failing_insert(*args, **kwargs):
            if "fail_db" in kwargs.get('title', ''):
                return False  # Simulate database failure
            return original_insert(*args, **kwargs)
        
        cm.db.insert_context = failing_insert
        
        # This should fail
        with pytest.raises(RuntimeError, match="Failed to store context in database"):
            cm.store_context("Database failure test", title="fail_db context")
        
        # Restore database and verify system works
        cm.db.insert_context = original_insert
        
        final_id = cm.store_context("Final recovery test", title="Final Context")
        final_retrieved = cm.retrieve_context(final_id)
        assert final_retrieved['data'] == "Final recovery test"
        
        # Clean up
        for ctx_id in [valid_id, recovery_id, final_id]:
            cm.delete_context(ctx_id)
        
        cm.close()


class TestConcurrentIntegration:
    """Test concurrent operations and thread safety."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_concurrent_context_operations(self, temp_db_path):
        """Test concurrent context operations across multiple threads."""
        cm = ContextManager(db_path=temp_db_path)
        
        results = {
            'store': [],
            'retrieve': [],
            'search': [],
            'update': [],
            'delete': [],
            'errors': []
        }
        
        # Pre-populate with some contexts for retrieval/update tests
        initial_contexts = []
        for i in range(20):
            context_id = cm.store_context(
                f"Initial context {i} for concurrent testing",
                title=f"Initial Context {i}",
                tags=["initial", f"item{i}"]
            )
            initial_contexts.append(context_id)
        
        def store_worker(worker_id, num_operations):
            """Worker that stores contexts."""
            try:
                for i in range(num_operations):
                    data = f"Concurrent store worker {worker_id} item {i} data"
                    title = f"Store Worker {worker_id} Item {i}"
                    tags = [f"worker{worker_id}", f"store", f"item{i}"]
                    
                    context_id = cm.store_context(data, title=title, tags=tags)
                    results['store'].append((worker_id, i, context_id))
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                results['errors'].append(f"Store worker {worker_id}: {str(e)}")
        
        def retrieve_worker(worker_id, num_operations):
            """Worker that retrieves contexts."""
            try:
                for i in range(num_operations):
                    context_id = initial_contexts[i % len(initial_contexts)]
                    retrieved = cm.retrieve_context(context_id)
                    results['retrieve'].append((worker_id, i, retrieved is not None))
                    time.sleep(0.001)
            except Exception as e:
                results['errors'].append(f"Retrieve worker {worker_id}: {str(e)}")
        
        def search_worker(worker_id, num_operations):
            """Worker that searches contexts."""
            try:
                search_terms = ["initial", "concurrent", "worker", "item"]
                for i in range(num_operations):
                    term = search_terms[i % len(search_terms)]
                    search_results = cm.search_contexts(term, limit=10)
                    results['search'].append((worker_id, i, len(search_results)))
                    time.sleep(0.002)
            except Exception as e:
                results['errors'].append(f"Search worker {worker_id}: {str(e)}")
        
        def update_worker(worker_id, num_operations):
            """Worker that updates contexts."""
            try:
                for i in range(num_operations):
                    context_id = initial_contexts[i % len(initial_contexts)]
                    new_title = f"Updated by worker {worker_id} iteration {i}"
                    success = cm.update_context(context_id, title=new_title)
                    results['update'].append((worker_id, i, success))
                    time.sleep(0.001)
            except Exception as e:
                results['errors'].append(f"Update worker {worker_id}: {str(e)}")
        
        # Start concurrent operations
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = []
            
            # Start store workers
            for worker_id in range(3):
                future = executor.submit(store_worker, worker_id, 10)
                futures.append(future)
            
            # Start retrieve workers
            for worker_id in range(3):
                future = executor.submit(retrieve_worker, worker_id, 15)
                futures.append(future)
            
            # Start search workers
            for worker_id in range(2):
                future = executor.submit(search_worker, worker_id, 8)
                futures.append(future)
            
            # Start update workers
            for worker_id in range(2):
                future = executor.submit(update_worker, worker_id, 5)
                futures.append(future)
            
            # Wait for all operations to complete
            for future in as_completed(futures):
                future.result()  # This will raise any exceptions
        
        # Verify results
        assert len(results['errors']) == 0, f"Concurrent operation errors: {results['errors']}"
        
        # Verify store operations
        assert len(results['store']) == 30  # 3 workers * 10 operations
        stored_ids = [result[2] for result in results['store']]
        assert len(set(stored_ids)) == 30  # All IDs should be unique
        
        # Verify retrieve operations
        assert len(results['retrieve']) == 45  # 3 workers * 15 operations
        assert all(success for _, _, success in results['retrieve'])
        
        # Verify search operations
        assert len(results['search']) == 16  # 2 workers * 8 operations
        assert all(count >= 0 for _, _, count in results['search'])
        
        # Verify update operations
        assert len(results['update']) == 10  # 2 workers * 5 operations
        assert all(success for _, _, success in results['update'])
        
        # Verify all stored contexts can be retrieved
        for _, _, context_id in results['store']:
            retrieved = cm.retrieve_context(context_id)
            assert "Concurrent store worker" in retrieved['data']
        
        # Clean up
        for context_id in initial_contexts + stored_ids:
            try:
                cm.delete_context(context_id)
            except RuntimeError:
                pass  # Context might have been deleted by another operation
        
        cm.close()
    
    def test_high_concurrency_stress(self, temp_db_path):
        """Test system under high concurrency stress."""
        cm = ContextManager(db_path=temp_db_path)
        
        num_threads = 20
        operations_per_thread = 25
        total_operations = num_threads * operations_per_thread
        
        completed_operations = []
        errors = []
        
        def stress_worker(worker_id):
            """Worker that performs mixed operations under stress."""
            try:
                local_contexts = []
                
                for i in range(operations_per_thread):
                    operation_type = i % 4  # Cycle through operation types
                    
                    if operation_type == 0:  # Store
                        data = f"Stress test data from worker {worker_id} operation {i}"
                        context_id = cm.store_context(data, title=f"Stress {worker_id}-{i}")
                        local_contexts.append(context_id)
                        completed_operations.append(('store', worker_id, i))
                    
                    elif operation_type == 1 and local_contexts:  # Retrieve
                        context_id = local_contexts[-1]  # Get most recent
                        retrieved = cm.retrieve_context(context_id)
                        assert retrieved is not None
                        completed_operations.append(('retrieve', worker_id, i))
                    
                    elif operation_type == 2:  # Search
                        results = cm.search_contexts("stress", limit=5)
                        completed_operations.append(('search', worker_id, len(results)))
                    
                    elif operation_type == 3 and local_contexts:  # Update
                        context_id = local_contexts[0]  # Update oldest
                        success = cm.update_context(context_id, title=f"Updated Stress {worker_id}-{i}")
                        completed_operations.append(('update', worker_id, success))
                    
                    # Small random delay to increase contention
                    time.sleep(0.001 * (worker_id % 3))
                
                # Clean up local contexts
                for context_id in local_contexts:
                    try:
                        cm.delete_context(context_id)
                        completed_operations.append(('delete', worker_id, True))
                    except RuntimeError:
                        pass  # Context might have been deleted already
                        
            except Exception as e:
                errors.append(f"Stress worker {worker_id}: {str(e)}")
        
        # Run stress test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_worker, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                future.result()  # Wait for completion and check for exceptions
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify results
        assert len(errors) == 0, f"Stress test errors: {errors}"
        assert len(completed_operations) >= total_operations  # Should have at least this many
        
        # Performance verification
        operations_per_second = len(completed_operations) / duration
        print(f"Stress test completed {len(completed_operations)} operations in {duration:.2f}s")
        print(f"Performance: {operations_per_second:.1f} operations/second")
        
        # Should handle at least 100 operations per second under stress
        assert operations_per_second > 100, f"Performance too low: {operations_per_second:.1f} ops/sec"
        
        # Verify database consistency after stress test
        final_stats = cm.get_stats()
        assert 'total_contexts' in final_stats
        assert final_stats['total_contexts'] >= 0  # Should be consistent
        
        cm.close()


class TestDataIntegrityIntegration:
    """Test data integrity across all operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_data_integrity_across_operations(self, temp_db_path):
        """Test that data integrity is maintained across all operations."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test data with various characteristics
        test_data = [
            {
                'data': 'Simple ASCII text for integrity testing',
                'title': 'ASCII Test',
                'tags': ['ascii', 'simple']
            },
            {
                'data': '你好世界 🌍 Unicode integrity test with emojis 🚀✨',
                'title': 'Unicode Test: 测试',
                'tags': ['unicode', '测试', '🏷️']
            },
            {
                'data': 'Data with\nnewlines\nand\ttabs\rand\x00null bytes',
                'title': 'Special Characters',
                'tags': ['special', 'chars']
            },
            {
                'data': 'A' * 10000,  # Large repetitive data
                'title': 'Large Compressible',
                'tags': ['large', 'compressible']
            },
            {
                'data': json.dumps({
                    'type': 'json',
                    'nested': {'key': 'value', 'number': 42},
                    'array': [1, 2, 3, 'string', True, None],
                    'unicode': '测试数据'
                }, ensure_ascii=False),
                'title': 'JSON Data',
                'tags': ['json', 'structured']
            }
        ]
        
        stored_contexts = []
        
        # Store all test data
        for i, test_case in enumerate(test_data):
            context_id = cm.store_context(
                test_case['data'],
                title=test_case['title'],
                tags=test_case['tags']
            )
            
            stored_contexts.append({
                'id': context_id,
                'original': test_case
            })
            
            # Immediately verify storage integrity
            retrieved = cm.retrieve_context(context_id)
            assert retrieved['data'] == test_case['data'], f"Data integrity failed for test case {i}"
            assert retrieved['title'] == test_case['title'], f"Title integrity failed for test case {i}"
            assert retrieved['tags'] == test_case['tags'], f"Tags integrity failed for test case {i}"
        
        # Test integrity after multiple operations
        for i, ctx in enumerate(stored_contexts):
            # Update each context
            updated_data = f"Updated: {ctx['original']['data']}"
            updated_title = f"Updated: {ctx['original']['title']}"
            updated_tags = ctx['original']['tags'] + ['updated']
            
            success = cm.update_context(ctx['id'], data=updated_data, title=updated_title, tags=updated_tags)
            assert success is True
            
            # Verify update integrity
            retrieved = cm.retrieve_context(ctx['id'])
            assert retrieved['data'] == updated_data, f"Update data integrity failed for context {i}"
            assert retrieved['title'] == updated_title, f"Update title integrity failed for context {i}"
            assert retrieved['tags'] == updated_tags, f"Update tags integrity failed for context {i}"
            
            # Update stored context for later verification
            ctx['updated'] = {
                'data': updated_data,
                'title': updated_title,
                'tags': updated_tags
            }
        
        # Test integrity across search operations
        for search_term in ['Updated', 'unicode', 'large', 'json']:
            search_results = cm.search_contexts(search_term)
            
            for result in search_results:
                # Find corresponding stored context
                stored_ctx = next((ctx for ctx in stored_contexts if ctx['id'] == result['id']), None)
                assert stored_ctx is not None, f"Search returned unknown context: {result['id']}"
                
                # Verify search result integrity
                assert result['title'] == stored_ctx['updated']['title']
                assert result['tags'] == stored_ctx['updated']['tags']
        
        # Test integrity across list operations
        all_contexts = cm.list_contexts(limit=100)
        
        for listed_ctx in all_contexts:
            stored_ctx = next((ctx for ctx in stored_contexts if ctx['id'] == listed_ctx['id']), None)
            if stored_ctx:  # Only check our test contexts
                assert listed_ctx['title'] == stored_ctx['updated']['title']
                assert listed_ctx['tags'] == stored_ctx['updated']['tags']
        
        # Test integrity after database operations
        db_stats = cm.get_stats()
        assert db_stats['total_contexts'] >= len(stored_contexts)
        
        # Final integrity check - retrieve all contexts again
        for ctx in stored_contexts:
            final_retrieved = cm.retrieve_context(ctx['id'])
            assert final_retrieved['data'] == ctx['updated']['data']
            assert final_retrieved['title'] == ctx['updated']['title']
            assert final_retrieved['tags'] == ctx['updated']['tags']
        
        # Clean up
        for ctx in stored_contexts:
            success = cm.delete_context(ctx['id'])
            assert success is True
            
            # Verify deletion integrity
            with pytest.raises(RuntimeError, match="not found"):
                cm.retrieve_context(ctx['id'])
        
        cm.close()
    
    def test_compression_decompression_integrity(self, temp_db_path):
        """Test that compression/decompression maintains data integrity."""
        # Test with different compression settings
        compression_configs = [
            {'min_size_threshold': 100, 'min_compression_ratio': 0.9, 'compression_level': 1},
            {'min_size_threshold': 500, 'min_compression_ratio': 0.8, 'compression_level': 6},
            {'min_size_threshold': 1000, 'min_compression_ratio': 0.7, 'compression_level': 9},
        ]
        
        for config_idx, config in enumerate(compression_configs):
            # Create context manager with specific compression config
            compression_engine = CompressionEngine(**config)
            cm = ContextManager(db_path=temp_db_path, compression_engine=compression_engine)
            
            # Test data of various sizes and types
            test_cases = [
                f"Small data {config_idx}",  # Below threshold
                f"Medium data {config_idx} " * 100,  # Above threshold, compressible
                ''.join(chr(ord('A') + (i % 26)) for i in range(2000)),  # Above threshold, less compressible
                f"Unicode test {config_idx}: 你好世界 🌍 " * 50,  # Unicode data
            ]
            
            for case_idx, test_data in enumerate(test_cases):
                context_id = cm.store_context(
                    test_data,
                    title=f"Compression Test {config_idx}-{case_idx}",
                    tags=[f"compression{config_idx}", f"case{case_idx}"]
                )
                
                # Retrieve and verify integrity
                retrieved = cm.retrieve_context(context_id)
                assert retrieved['data'] == test_data, f"Compression integrity failed for config {config_idx}, case {case_idx}"
                
                # Verify compression metadata
                metadata = retrieved['metadata']
                assert 'compression_method' in metadata
                assert 'original_size' in metadata
                assert 'compressed_size' in metadata
                assert metadata['original_size'] == len(test_data.encode('utf-8'))
                
                # Clean up
                cm.delete_context(context_id)
            
            cm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])