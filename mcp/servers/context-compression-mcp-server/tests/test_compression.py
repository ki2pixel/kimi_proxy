"""
Unit tests for the compression engine module.

Tests compression and decompression functionality with various data sizes,
types, and edge cases.
"""

import pytest
import zlib
from src.compression import CompressionEngine, CompressionResult


class TestCompressionEngine:
    """Test cases for CompressionEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = CompressionEngine()
    
    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        engine = CompressionEngine()
        assert engine.min_size_threshold == 1024
        assert engine.min_compression_ratio == 0.8
        assert engine.compression_level == 6
    
    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        engine = CompressionEngine(
            min_size_threshold=512,
            min_compression_ratio=0.7,
            compression_level=9
        )
        assert engine.min_size_threshold == 512
        assert engine.min_compression_ratio == 0.7
        assert engine.compression_level == 9
    
    def test_compress_empty_data(self):
        """Test compression with empty data raises ValueError."""
        with pytest.raises(ValueError, match="Data cannot be empty or None"):
            self.engine.compress("")
        
        with pytest.raises(ValueError, match="Data cannot be empty or None"):
            self.engine.compress(None)
    
    def test_compress_small_data_no_compression(self):
        """Test that small data is not compressed."""
        small_data = "Hello, World!"  # Less than 1KB
        result = self.engine.compress(small_data)
        
        assert isinstance(result, CompressionResult)
        assert result.compression_method == "none"
        assert result.compression_ratio == 1.0
        assert result.original_size == len(small_data.encode('utf-8'))
        assert result.compressed_size == result.original_size
        assert result.compressed_data == small_data.encode('utf-8')
    
    def test_compress_large_compressible_data(self):
        """Test compression of large, highly compressible data."""
        # Create highly repetitive data that compresses well
        large_data = "A" * 2000  # 2KB of repeated characters
        result = self.engine.compress(large_data)
        
        assert isinstance(result, CompressionResult)
        assert result.compression_method == "zlib"
        assert result.compression_ratio < 0.8  # Should compress well
        assert result.original_size == 2000
        assert result.compressed_size < result.original_size
    
    def test_compress_large_incompressible_data(self):
        """Test compression of large data that doesn't compress well."""
        # Create pseudo-random data that doesn't compress well
        import random
        random.seed(42)  # For reproducible tests
        large_data = ''.join(chr(random.randint(32, 126)) for _ in range(2000))
        
        result = self.engine.compress(large_data)
        
        assert isinstance(result, CompressionResult)
        # Should fallback to uncompressed due to poor compression ratio
        # (This might be "zlib" or "none" depending on actual compression ratio)
        assert result.original_size == 2000
    
    def test_compress_unicode_data(self):
        """Test compression with Unicode characters."""
        unicode_data = "Hello 世界! 🌍 " * 100  # Mix of ASCII, Chinese, and emoji
        result = self.engine.compress(unicode_data)
        
        assert isinstance(result, CompressionResult)
        assert result.original_size > 0
        assert result.compressed_size > 0
    
    def test_decompress_zlib_data(self):
        """Test decompression of zlib-compressed data."""
        original_data = "This is a test string that will be compressed." * 50
        compressed_bytes = zlib.compress(original_data.encode('utf-8'))
        
        decompressed = self.engine.decompress(compressed_bytes, "zlib")
        assert decompressed == original_data
    
    def test_decompress_uncompressed_data(self):
        """Test decompression of uncompressed data."""
        original_data = "This is uncompressed data."
        data_bytes = original_data.encode('utf-8')
        
        decompressed = self.engine.decompress(data_bytes, "none")
        assert decompressed == original_data
    
    def test_decompress_invalid_method(self):
        """Test decompression with invalid compression method."""
        data_bytes = b"some data"
        
        with pytest.raises(ValueError, match="Unsupported compression method"):
            self.engine.decompress(data_bytes, "invalid_method")
    
    def test_decompress_none_data(self):
        """Test decompression with None data."""
        with pytest.raises(ValueError, match="Compressed data cannot be None"):
            self.engine.decompress(None, "zlib")
    
    def test_decompress_corrupted_zlib_data(self):
        """Test decompression of corrupted zlib data."""
        corrupted_data = b"this is not valid zlib data"
        
        with pytest.raises(RuntimeError, match="Decompression failed"):
            self.engine.decompress(corrupted_data, "zlib")
    
    def test_decompress_invalid_utf8(self):
        """Test decompression resulting in invalid UTF-8."""
        # Create invalid UTF-8 bytes
        invalid_utf8 = b'\xff\xfe\xfd'
        
        with pytest.raises(RuntimeError, match="Failed to decode decompressed data"):
            self.engine.decompress(invalid_utf8, "none")
    
    def test_calculate_compression_ratio(self):
        """Test compression ratio calculation."""
        ratio = self.engine.calculate_compression_ratio(1000, 300)
        assert ratio == 0.3
        
        ratio = self.engine.calculate_compression_ratio(100, 100)
        assert ratio == 1.0
        
        ratio = self.engine.calculate_compression_ratio(100, 150)
        assert ratio == 1.5
    
    def test_calculate_compression_ratio_invalid_sizes(self):
        """Test compression ratio calculation with invalid sizes."""
        with pytest.raises(ValueError, match="Original size must be positive"):
            self.engine.calculate_compression_ratio(0, 100)
        
        with pytest.raises(ValueError, match="Original size must be positive"):
            self.engine.calculate_compression_ratio(-100, 50)
        
        with pytest.raises(ValueError, match="Compressed size cannot be negative"):
            self.engine.calculate_compression_ratio(100, -50)
    
    def test_get_compression_stats_empty_data(self):
        """Test compression stats for empty data."""
        stats = self.engine.get_compression_stats("")
        
        assert stats["original_size"] == 0
        assert stats["would_compress"] is False
        assert "Empty data" in stats["reason"]
    
    def test_get_compression_stats_small_data(self):
        """Test compression stats for small data."""
        small_data = "Hello!"
        stats = self.engine.get_compression_stats(small_data)
        
        assert stats["original_size"] == len(small_data.encode('utf-8'))
        assert stats["would_compress"] is False
        assert "Below minimum threshold" in stats["reason"]
    
    def test_get_compression_stats_large_compressible_data(self):
        """Test compression stats for large compressible data."""
        large_data = "A" * 2000
        stats = self.engine.get_compression_stats(large_data)
        
        assert stats["original_size"] == 2000
        assert "compressed_size" in stats
        assert "compression_ratio" in stats
        assert stats["would_compress"] is True
        assert "Good compression" in stats["reason"]
    
    def test_round_trip_compression_decompression(self):
        """Test complete round-trip compression and decompression."""
        test_cases = [
            "Simple ASCII text that should compress well." * 100,
            "Mixed content with numbers 123456789 and symbols !@#$%^&*()" * 50,
            "Unicode test: 你好世界 🌍 Здравствуй мир 🌎 مرحبا بالعالم 🌏" * 30,
            "JSON-like data: " + '{"key": "value", "number": 42, "array": [1,2,3]}' * 40
        ]
        
        for original_data in test_cases:
            # Compress
            result = self.engine.compress(original_data)
            
            # Decompress
            decompressed = self.engine.decompress(
                result.compressed_data, 
                result.compression_method
            )
            
            # Verify round-trip integrity
            assert decompressed == original_data
    
    def test_compression_with_different_levels(self):
        """Test compression with different compression levels."""
        test_data = "This is test data for compression level testing." * 100
        
        results = []
        for level in [1, 6, 9]:  # Fast, default, best compression
            engine = CompressionEngine(compression_level=level)
            result = engine.compress(test_data)
            results.append((level, result.compressed_size))
        
        # Higher compression levels should generally produce smaller results
        # (though this isn't guaranteed for all data types)
        assert all(result[1] > 0 for result in results)
    
    def test_compression_threshold_behavior(self):
        """Test behavior at compression threshold boundaries."""
        # Test data right at the threshold
        threshold_data = "A" * 1024  # Exactly at threshold
        result = self.engine.compress(threshold_data)
        
        # Should attempt compression since it's at threshold
        assert result.original_size == 1024
        
        # Test data just below threshold
        below_threshold_data = "A" * 1023
        result = self.engine.compress(below_threshold_data)
        
        assert result.compression_method == "none"
        assert result.compression_ratio == 1.0
    
    def test_compression_with_extreme_data_sizes(self):
        """Test compression with very small and very large data."""
        # Test with single character
        single_char = "A"
        result = self.engine.compress(single_char)
        assert result.compression_method == "none"
        assert result.original_size == 1
        
        # Test with very large data (10MB)
        large_data = "A" * (10 * 1024 * 1024)
        result = self.engine.compress(large_data)
        assert result.original_size == 10 * 1024 * 1024
        # Should compress very well due to repetitive nature
        assert result.compression_method == "zlib"
        assert result.compression_ratio < 0.01  # Should compress to less than 1%
    
    def test_compression_with_binary_like_strings(self):
        """Test compression with strings that look like binary data."""
        import random
        random.seed(42)  # For reproducible tests
        
        # Create pseudo-random string that doesn't compress well
        random_chars = ''.join(chr(random.randint(32, 126)) for _ in range(5000))
        result = self.engine.compress(random_chars)
        
        # Should still work, but may not compress well
        assert result.original_size == 5000
        assert result.compressed_size > 0
        
        # Test round-trip
        decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
        assert decompressed == random_chars
    
    def test_compression_error_handling_edge_cases(self):
        """Test compression error handling with edge cases."""
        # Test with string containing null bytes
        null_data = "Hello\x00World\x00Test"
        result = self.engine.compress(null_data)
        assert result.original_size == len(null_data.encode('utf-8'))
        
        # Test round-trip with null bytes
        decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
        assert decompressed == null_data
        
        # Test with string containing all possible UTF-8 characters
        utf8_test = "".join(chr(i) for i in range(32, 127))  # Printable ASCII
        utf8_test += "你好世界🌍"  # Unicode
        result = self.engine.compress(utf8_test)
        
        decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
        assert decompressed == utf8_test
    
    def test_decompression_with_corrupted_data_variations(self):
        """Test decompression with various types of corrupted data."""
        # Test with truncated zlib data
        original_data = "This is test data for corruption testing." * 50
        compressed = zlib.compress(original_data.encode('utf-8'))
        truncated = compressed[:-10]  # Remove last 10 bytes
        
        with pytest.raises(RuntimeError, match="Decompression failed"):
            self.engine.decompress(truncated, "zlib")
        
        # Test with completely invalid zlib header
        invalid_header = b'\x00\x01\x02\x03' + b'invalid data' * 10
        with pytest.raises(RuntimeError, match="Decompression failed"):
            self.engine.decompress(invalid_header, "zlib")
        
        # Test with empty bytes for zlib
        with pytest.raises(RuntimeError, match="Decompression failed"):
            self.engine.decompress(b"", "zlib")
    
    def test_compression_performance_characteristics(self):
        """Test compression performance with different data patterns."""
        import time
        
        # Test with highly repetitive data (should compress fast and well)
        repetitive_data = "ABCD" * 1000  # 4KB of repetitive data
        start_time = time.time()
        result = self.engine.compress(repetitive_data)
        compress_time = time.time() - start_time
        
        assert result.compression_method == "zlib"
        assert result.compression_ratio < 0.1  # Should compress very well
        assert compress_time < 1.0  # Should be fast
        
        # Test decompression performance
        start_time = time.time()
        decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
        decompress_time = time.time() - start_time
        
        assert decompressed == repetitive_data
        assert decompress_time < 1.0  # Should be fast
    
    def test_compression_with_different_encodings(self):
        """Test compression behavior with different text encodings."""
        # Test with various Unicode categories
        test_strings = [
            "ASCII only text",
            "Latin-1: café, naïve, résumé",
            "Cyrillic: Привет мир",
            "Chinese: 你好世界",
            "Japanese: こんにちは世界",
            "Arabic: مرحبا بالعالم",
            "Emoji: 🌍🌎🌏 Hello World! 🚀✨",
            "Mixed: Hello 世界 🌍 Привет café"
        ]
        
        for test_string in test_strings:
            result = self.engine.compress(test_string)
            assert result.original_size == len(test_string.encode('utf-8'))
            
            # Test round-trip
            decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
            assert decompressed == test_string
    
    def test_compression_ratio_edge_cases(self):
        """Test compression ratio calculation with edge cases."""
        # Test with identical sizes
        ratio = self.engine.calculate_compression_ratio(1000, 1000)
        assert ratio == 1.0
        
        # Test with expansion (compressed larger than original)
        ratio = self.engine.calculate_compression_ratio(100, 150)
        assert ratio == 1.5
        
        # Test with very small original size
        ratio = self.engine.calculate_compression_ratio(1, 1)
        assert ratio == 1.0
        
        # Test with zero compressed size
        ratio = self.engine.calculate_compression_ratio(1000, 0)
        assert ratio == 0.0
        
        # Test with very large numbers
        ratio = self.engine.calculate_compression_ratio(1000000000, 500000000)
        assert ratio == 0.5
    
    def test_compression_stats_comprehensive(self):
        """Test compression stats with comprehensive scenarios."""
        # Test with data that will definitely compress
        compressible_data = "A" * 5000
        stats = self.engine.get_compression_stats(compressible_data)
        
        assert stats["original_size"] == 5000
        assert stats["would_compress"] is True
        assert "compressed_size" in stats
        assert stats["compression_ratio"] < 0.8
        
        # Test with data that won't compress well
        import random
        random.seed(42)
        incompressible_data = ''.join(chr(random.randint(32, 126)) for _ in range(5000))
        stats = self.engine.get_compression_stats(incompressible_data)
        
        assert stats["original_size"] == 5000
        # May or may not compress depending on randomness, but should have stats
        assert "compressed_size" in stats
        assert "compression_ratio" in stats
        assert "would_compress" in stats
    
    def test_concurrent_compression_operations(self):
        """Test thread safety of compression operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def compress_worker(worker_id):
            try:
                for i in range(10):
                    data = f"Worker {worker_id} data item {i} " * 100
                    result = self.engine.compress(data)
                    decompressed = self.engine.decompress(result.compressed_data, result.compression_method)
                    results.append((worker_id, i, data == decompressed))
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple compression threads
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=compress_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Compression thread errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations each
        assert all(success for _, _, success in results)  # All round-trips should succeed


class TestCompressionResult:
    """Test cases for CompressionResult dataclass."""
    
    def test_compression_result_creation(self):
        """Test creation of CompressionResult."""
        result = CompressionResult(
            compressed_data=b"test data",
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            compression_ratio=0.5
        )
        
        assert result.compressed_data == b"test data"
        assert result.original_size == 100
        assert result.compressed_size == 50
        assert result.compression_method == "zlib"
        assert result.compression_ratio == 0.5


if __name__ == "__main__":
    pytest.main([__file__])