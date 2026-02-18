"""
Compression engine for context data using zlib compression.

This module provides compression and decompression functionality with
intelligent fallback handling for data that doesn't compress well.
"""

import zlib
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class CompressionResult:
    """Result of compression operation with metadata."""
    compressed_data: bytes
    original_size: int
    compressed_size: int
    compression_method: str
    compression_ratio: float


class CompressionEngine:
    """
    Handles compression and decompression of context data.
    
    Uses zlib as the primary compression algorithm with intelligent
    fallback to uncompressed storage when compression doesn't provide
    significant benefits.
    """
    
    # Configuration constants
    MIN_SIZE_THRESHOLD = 1024  # Only compress data larger than 1KB
    MIN_COMPRESSION_RATIO = 0.8  # Only use compression if it achieves <80% of original size
    COMPRESSION_LEVEL = 6  # Balance between speed and compression ratio
    
    def __init__(self, 
                 min_size_threshold: int = MIN_SIZE_THRESHOLD,
                 min_compression_ratio: float = MIN_COMPRESSION_RATIO,
                 compression_level: int = COMPRESSION_LEVEL):
        """
        Initialize compression engine with configurable parameters.
        
        Args:
            min_size_threshold: Minimum data size to attempt compression
            min_compression_ratio: Maximum ratio to consider compression worthwhile
            compression_level: zlib compression level (1-9, 6 is default)
        """
        self.min_size_threshold = min_size_threshold
        self.min_compression_ratio = min_compression_ratio
        self.compression_level = compression_level
    
    def compress(self, data: str) -> CompressionResult:
        """
        Compress string data using zlib with intelligent fallback.
        
        Args:
            data: String data to compress
            
        Returns:
            CompressionResult with compressed data and metadata
            
        Raises:
            ValueError: If data is empty or None
        """
        if not data:
            raise ValueError("Data cannot be empty or None")
        
        # Convert string to bytes
        data_bytes = data.encode('utf-8')
        original_size = len(data_bytes)
        
        # Check if data is large enough to warrant compression
        if original_size < self.min_size_threshold:
            return CompressionResult(
                compressed_data=data_bytes,
                original_size=original_size,
                compressed_size=original_size,
                compression_method="none",
                compression_ratio=1.0
            )
        
        try:
            # Attempt compression
            compressed_data = zlib.compress(data_bytes, level=self.compression_level)
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / original_size
            
            # Check if compression is worthwhile
            if compression_ratio <= self.min_compression_ratio:
                return CompressionResult(
                    compressed_data=compressed_data,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_method="zlib",
                    compression_ratio=compression_ratio
                )
            else:
                # Compression didn't help much, store uncompressed
                return CompressionResult(
                    compressed_data=data_bytes,
                    original_size=original_size,
                    compressed_size=original_size,
                    compression_method="none",
                    compression_ratio=1.0
                )
                
        except Exception as e:
            # Fallback to uncompressed on any compression error
            return CompressionResult(
                compressed_data=data_bytes,
                original_size=original_size,
                compressed_size=original_size,
                compression_method="none",
                compression_ratio=1.0
            )
    
    def decompress(self, compressed_data: bytes, compression_method: str) -> str:
        """
        Decompress data based on the compression method used.
        
        Args:
            compressed_data: Compressed data bytes
            compression_method: Method used for compression ("zlib" or "none")
            
        Returns:
            Original string data
            
        Raises:
            ValueError: If compressed_data is None or compression_method is invalid
            RuntimeError: If decompression fails
        """
        if compressed_data is None:
            raise ValueError("Compressed data cannot be None")
        
        if compression_method not in ["zlib", "none"]:
            raise ValueError(f"Unsupported compression method: {compression_method}")
        
        try:
            if compression_method == "zlib":
                # Decompress using zlib
                decompressed_bytes = zlib.decompress(compressed_data)
            else:
                # Data was stored uncompressed
                decompressed_bytes = compressed_data
            
            # Convert bytes back to string
            return decompressed_bytes.decode('utf-8')
            
        except zlib.error as e:
            raise RuntimeError(f"Decompression failed: {str(e)}")
        except UnicodeDecodeError as e:
            raise RuntimeError(f"Failed to decode decompressed data: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during decompression: {str(e)}")
    
    def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """
        Calculate compression ratio.
        
        Args:
            original_size: Size of original data in bytes
            compressed_size: Size of compressed data in bytes
            
        Returns:
            Compression ratio (compressed_size / original_size)
            
        Raises:
            ValueError: If sizes are invalid
        """
        if original_size <= 0:
            raise ValueError("Original size must be positive")
        if compressed_size < 0:
            raise ValueError("Compressed size cannot be negative")
        
        return compressed_size / original_size
    
    def get_compression_stats(self, data: str) -> dict:
        """
        Get compression statistics for given data without actually compressing.
        
        Args:
            data: String data to analyze
            
        Returns:
            Dictionary with compression statistics
        """
        if not data:
            return {
                "original_size": 0,
                "would_compress": False,
                "reason": "Empty data"
            }
        
        data_bytes = data.encode('utf-8')
        original_size = len(data_bytes)
        
        if original_size < self.min_size_threshold:
            return {
                "original_size": original_size,
                "would_compress": False,
                "reason": f"Below minimum threshold ({self.min_size_threshold} bytes)"
            }
        
        try:
            # Test compression
            compressed_data = zlib.compress(data_bytes, level=self.compression_level)
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / original_size
            
            would_compress = compression_ratio <= self.min_compression_ratio
            
            return {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "would_compress": would_compress,
                "reason": "Good compression" if would_compress else "Poor compression ratio"
            }
            
        except Exception as e:
            return {
                "original_size": original_size,
                "would_compress": False,
                "reason": f"Compression error: {str(e)}"
            }