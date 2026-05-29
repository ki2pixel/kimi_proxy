"""
Unit tests for database operations.
"""

import unittest
import tempfile
import os
import json
import threading
import time
from unittest.mock import patch, MagicMock

from src.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Test cases for DatabaseManager class."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test database."""
        self.db_manager.close_connections()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database initialization and schema creation."""
        # Database should be initialized automatically
        self.assertTrue(self.db_manager.verify_schema())
        
        # Check database info
        info = self.db_manager.get_database_info()
        self.assertEqual(info['context_count'], 0)
        self.assertTrue(info['schema_valid'])
        self.assertEqual(info['db_path'], self.temp_db.name)
    
    def test_insert_context(self):
        """Test inserting context records."""
        # Test successful insertion
        result = self.db_manager.insert_context(
            context_id="test_001",
            title="Test Context",
            original_size=1000,
            compressed_size=500,
            compression_method="zlib",
            data=b"compressed_data",
            tags='["test", "example"]'
        )
        self.assertTrue(result)
        
        # Test duplicate insertion (should fail)
        result = self.db_manager.insert_context(
            context_id="test_001",
            title="Duplicate Context",
            original_size=2000,
            compressed_size=1000,
            compression_method="zlib",
            data=b"other_data"
        )
        self.assertFalse(result)
    
    def test_select_context(self):
        """Test selecting context records."""
        # Insert test data
        self.db_manager.insert_context(
            context_id="test_002",
            title="Select Test",
            original_size=1500,
            compressed_size=750,
            compression_method="gzip",
            data=b"test_data",
            tags='["select", "test"]'
        )
        
        # Test successful selection
        context = self.db_manager.select_context("test_002")
        self.assertIsNotNone(context)
        self.assertEqual(context['id'], "test_002")
        self.assertEqual(context['title'], "Select Test")
        self.assertEqual(context['original_size'], 1500)
        self.assertEqual(context['compressed_size'], 750)
        self.assertEqual(context['compression_method'], "gzip")
        self.assertEqual(context['data'], b"test_data")
        self.assertEqual(context['tags'], '["select", "test"]')
        
        # Test non-existent context
        context = self.db_manager.select_context("non_existent")
        self.assertIsNone(context)
    
    def test_update_context(self):
        """Test updating context records."""
        # Insert test data
        self.db_manager.insert_context(
            context_id="test_003",
            title="Original Title",
            original_size=1000,
            compressed_size=500,
            compression_method="zlib",
            data=b"original_data",
            tags='["original"]'
        )
        
        # Test successful update
        result = self.db_manager.update_context(
            context_id="test_003",
            title="Updated Title",
            tags='["updated", "modified"]'
        )
        self.assertTrue(result)
        
        # Verify update
        context = self.db_manager.select_context("test_003")
        self.assertEqual(context['title'], "Updated Title")
        self.assertEqual(context['tags'], '["updated", "modified"]')
        self.assertEqual(context['original_size'], 1000)  # Unchanged
        
        # Test update non-existent context
        result = self.db_manager.update_context(
            context_id="non_existent",
            title="New Title"
        )
        self.assertFalse(result)
        
        # Test update with no fields
        result = self.db_manager.update_context("test_003")
        self.assertFalse(result)
    
    def test_delete_context(self):
        """Test deleting context records."""
        # Insert test data
        self.db_manager.insert_context(
            context_id="test_004",
            title="Delete Test",
            original_size=1000,
            compressed_size=500,
            compression_method="zlib",
            data=b"delete_data"
        )
        
        # Verify context exists
        self.assertTrue(self.db_manager.context_exists("test_004"))
        
        # Test successful deletion
        result = self.db_manager.delete_context("test_004")
        self.assertTrue(result)
        
        # Verify context is deleted
        self.assertFalse(self.db_manager.context_exists("test_004"))
        
        # Test delete non-existent context
        result = self.db_manager.delete_context("non_existent")
        self.assertFalse(result)
    
    def test_search_contexts(self):
        """Test searching context records."""
        # Insert test data
        test_contexts = [
            ("search_001", "Python Documentation", '["python", "plan"]'),
            ("search_002", "JavaScript Guide", '["javascript", "tutorial"]'),
            ("search_003", "Python Tutorial", '["python", "beginner"]'),
            ("search_004", "Database Design", '["database", "sql"]')
        ]
        
        for ctx_id, title, tags in test_contexts:
            self.db_manager.insert_context(
                context_id=ctx_id,
                title=title,
                original_size=1000,
                compressed_size=500,
                compression_method="zlib",
                data=b"test_data",
                tags=tags
            )
        
        # Test title search
        results = self.db_manager.search_contexts("Python")
        self.assertEqual(len(results), 2)
        titles = [r['title'] for r in results]
        self.assertIn("Python Documentation", titles)
        self.assertIn("Python Tutorial", titles)
        
        # Test tag search
        results = self.db_manager.search_contexts("javascript")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "JavaScript Guide")
        
        # Test no results
        results = self.db_manager.search_contexts("nonexistent")
        self.assertEqual(len(results), 0)
        
        # Test limit and offset
        results = self.db_manager.search_contexts("", limit=2, offset=1)
        self.assertEqual(len(results), 2)
    
    def test_list_contexts(self):
        """Test listing all contexts."""
        # Insert test data
        for i in range(5):
            self.db_manager.insert_context(
                context_id=f"list_{i:03d}",
                title=f"Context {i}",
                original_size=1000,
                compressed_size=500,
                compression_method="zlib",
                data=b"test_data"
            )
        
        # Test list all
        results = self.db_manager.list_contexts()
        self.assertEqual(len(results), 5)
        
        # Test limit
        results = self.db_manager.list_contexts(limit=3)
        self.assertEqual(len(results), 3)
        
        # Test offset
        results = self.db_manager.list_contexts(limit=2, offset=2)
        self.assertEqual(len(results), 2)
        
        # Verify data fields are not included
        for result in results:
            self.assertNotIn('data', result)
    
    def test_context_exists(self):
        """Test checking if context exists."""
        # Test non-existent context
        self.assertFalse(self.db_manager.context_exists("test_exists"))
        
        # Insert context
        self.db_manager.insert_context(
            context_id="test_exists",
            title="Exists Test",
            original_size=1000,
            compressed_size=500,
            compression_method="zlib",
            data=b"test_data"
        )
        
        # Test existing context
        self.assertTrue(self.db_manager.context_exists("test_exists"))
    
    def test_get_context_count(self):
        """Test getting context count."""
        # Initially empty
        self.assertEqual(self.db_manager.get_context_count(), 0)
        
        # Add contexts
        for i in range(3):
            self.db_manager.insert_context(
                context_id=f"count_{i}",
                title=f"Count Test {i}",
                original_size=1000,
                compressed_size=500,
                compression_method="zlib",
                data=b"test_data"
            )
        
        self.assertEqual(self.db_manager.get_context_count(), 3)
    
    def test_thread_safety(self):
        """Test thread-safe database operations."""
        results = []
        errors = []
        
        def insert_contexts(thread_id):
            try:
                for i in range(10):
                    context_id = f"thread_{thread_id}_{i:03d}"
                    result = self.db_manager.insert_context(
                        context_id=context_id,
                        title=f"Thread {thread_id} Context {i}",
                        original_size=1000,
                        compressed_size=500,
                        compression_method="zlib",
                        data=b"thread_data"
                    )
                    results.append((thread_id, i, result))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=insert_contexts, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(len(results), 50)  # 5 threads * 10 contexts each
        
        # Verify all contexts were inserted
        final_count = self.db_manager.get_context_count()
        self.assertEqual(final_count, 50)
    
    def test_concurrent_read_write_operations(self):
        """Test concurrent read and write operations."""
        # Insert initial data
        for i in range(10):
            self.db_manager.insert_context(
                context_id=f"concurrent_{i}",
                title=f"Concurrent Test {i}",
                original_size=1000,
                compressed_size=500,
                compression_method="zlib",
                data=b"concurrent_data"
            )
        
        read_results = []
        write_results = []
        errors = []
        
        def read_worker():
            try:
                for i in range(20):
                    context_id = f"concurrent_{i % 10}"
                    result = self.db_manager.select_context(context_id)
                    read_results.append(result is not None)
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(f"Read error: {str(e)}")
        
        def write_worker(worker_id):
            try:
                for i in range(5):
                    context_id = f"write_worker_{worker_id}_{i}"
                    result = self.db_manager.insert_context(
                        context_id=context_id,
                        title=f"Write Worker {worker_id} Context {i}",
                        original_size=1000,
                        compressed_size=500,
                        compression_method="zlib",
                        data=b"write_worker_data"
                    )
                    write_results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Write error: {str(e)}")
        
        # Start concurrent operations
        threads = []
        
        # Start read threads
        for _ in range(3):
            thread = threading.Thread(target=read_worker)
            threads.append(thread)
            thread.start()
        
        # Start write threads
        for worker_id in range(2):
            thread = threading.Thread(target=write_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Concurrent operation errors: {errors}")
        self.assertEqual(len(read_results), 60)  # 3 threads * 20 reads each
        self.assertEqual(len(write_results), 10)  # 2 threads * 5 writes each
        self.assertTrue(all(read_results))  # All reads should succeed
        self.assertTrue(all(write_results))  # All writes should succeed
    
    def test_database_corruption_recovery(self):
        """Test database behavior with corrupted data."""
        # Insert valid data first
        self.db_manager.insert_context(
            context_id="valid_context",
            title="Valid Context",
            original_size=1000,
            compressed_size=500,
            compression_method="zlib",
            data=b"valid_data"
        )
        
        # Try to insert data with invalid compression method
        result = self.db_manager.insert_context(
            context_id="invalid_compression",
            title="Invalid Compression",
            original_size=1000,
            compressed_size=500,
            compression_method="invalid_method",
            data=b"some_data"
        )
        # Should still succeed (database doesn't validate compression method)
        self.assertTrue(result)
        
        # Verify database is still functional
        context = self.db_manager.select_context("valid_context")
        self.assertIsNotNone(context)
        self.assertEqual(context['title'], "Valid Context")
    
    def test_large_data_handling(self):
        """Test database operations with large data."""
        # Create large data (1MB)
        large_data = b"x" * (1024 * 1024)
        
        result = self.db_manager.insert_context(
            context_id="large_data_test",
            title="Large Data Test",
            original_size=len(large_data),
            compressed_size=len(large_data) // 2,  # Simulated compression
            compression_method="zlib",
            data=large_data
        )
        
        self.assertTrue(result)
        
        # Retrieve large data
        context = self.db_manager.select_context("large_data_test")
        self.assertIsNotNone(context)
        self.assertEqual(len(context['data']), len(large_data))
        self.assertEqual(context['data'], large_data)
    
    def test_special_characters_handling(self):
        """Test database operations with special characters."""
        special_chars_data = "Special chars: 你好世界 🌍 ñáéíóú àèìòù äëïöü ß".encode('utf-8')
        
        result = self.db_manager.insert_context(
            context_id="special_chars_test",
            title="Special Characters: 你好世界 🌍",
            original_size=len(special_chars_data),
            compressed_size=len(special_chars_data),
            compression_method="none",
            data=special_chars_data,
            tags='["unicode", "特殊字符", "🏷️"]'
        )
        
        self.assertTrue(result)
        
        # Retrieve and verify
        context = self.db_manager.select_context("special_chars_test")
        self.assertIsNotNone(context)
        self.assertEqual(context['title'], "Special Characters: 你好世界 🌍")
        self.assertEqual(context['data'], special_chars_data)
        self.assertEqual(context['tags'], '["unicode", "特殊字符", "🏷️"]')
    
    def test_database_limits_and_edge_cases(self):
        """Test database behavior at limits and edge cases."""
        # Test empty title
        result = self.db_manager.insert_context(
            context_id="empty_title",
            title="",
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            data=b"test_data"
        )
        self.assertTrue(result)
        
        # Test None title
        result = self.db_manager.insert_context(
            context_id="none_title",
            title=None,
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            data=b"test_data"
        )
        self.assertTrue(result)
        
        # Test very long title
        long_title = "x" * 10000
        result = self.db_manager.insert_context(
            context_id="long_title",
            title=long_title,
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            data=b"test_data"
        )
        self.assertTrue(result)
        
        # Verify retrieval
        context = self.db_manager.select_context("long_title")
        self.assertEqual(context['title'], long_title)
        
        # Test zero sizes
        result = self.db_manager.insert_context(
            context_id="zero_sizes",
            title="Zero Sizes",
            original_size=0,
            compressed_size=0,
            compression_method="none",
            data=b""
        )
        self.assertTrue(result)
    
    def test_search_edge_cases(self):
        """Test search functionality with edge cases."""
        # Insert test data with various patterns
        test_data = [
            ("search_1", "Test with UPPERCASE", '["UPPER", "case"]'),
            ("search_2", "test with lowercase", '["lower", "case"]'),
            ("search_3", "Test with MiXeD cAsE", '["MiXeD", "CaSe"]'),
            ("search_4", "Special chars: @#$%^&*()", '["special", "@#$%"]'),
            ("search_5", "Numbers 12345", '["numbers", "12345"]'),
            ("search_6", "", '["empty", "title"]'),  # Empty title
            ("search_7", None, None),  # None title and tags
        ]
        
        for ctx_id, title, tags in test_data:
            self.db_manager.insert_context(
                context_id=ctx_id,
                title=title,
                original_size=100,
                compressed_size=50,
                compression_method="zlib",
                data=b"test_data",
                tags=tags
            )
        
        # Test case-insensitive search (SQLite LIKE is case-insensitive by default)
        results = self.db_manager.search_contexts("test")
        self.assertGreaterEqual(len(results), 3)  # Should find multiple matches
        
        # Test special character search
        results = self.db_manager.search_contexts("@#$%")
        self.assertEqual(len(results), 1)
        
        # Test number search
        results = self.db_manager.search_contexts("12345")
        self.assertEqual(len(results), 1)
        
        # Test empty query handling (should be handled by calling code)
        results = self.db_manager.search_contexts("")
        # Empty query should still work at database level
        self.assertIsInstance(results, list)
        
        # Test very long query
        long_query = "x" * 1000
        results = self.db_manager.search_contexts(long_query)
        self.assertEqual(len(results), 0)  # Should not match anything
    
    def test_error_handling(self):
        """Test error handling in database operations."""
        # Test with connection failure during operations
        with patch.object(self.db_manager, '_get_connection') as mock_get_conn:
            mock_get_conn.side_effect = Exception("Connection failed")
            
            # This should handle the error gracefully
            result = self.db_manager.insert_context(
                context_id="error_test",
                title="Error Test",
                original_size=1000,
                compressed_size=500,
                compression_method="zlib",
                data=b"test_data"
            )
            self.assertFalse(result)
            
            # Test other operations also handle errors gracefully
            context = self.db_manager.select_context("error_test")
            self.assertIsNone(context)
            
            results = self.db_manager.search_contexts("test")
            self.assertEqual(len(results), 0)
            
            count = self.db_manager.get_context_count()
            self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()