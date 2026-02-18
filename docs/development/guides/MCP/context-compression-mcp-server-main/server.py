from fastmcp import FastMCP
from typing import Optional, List, Dict, Any, Union
import logging

from src.context_manager import ContextManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(name="ContextCompressionMCP")

# Initialize context manager
context_manager = ContextManager()


def create_validation_error_response(
    param_name: str,
    received_value: Any,
    expected_types: List[str],
    validation_error: Optional[str] = None,
    context_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized validation error response.
    
    Args:
        param_name: Name of the parameter that failed validation
        received_value: The actual value that was received
        expected_types: List of expected type descriptions
        validation_error: Optional detailed validation error message
        context_id: Optional context ID for operations that involve existing contexts
        
    Returns:
        Dictionary with standardized error response format
    """
    received_type = type(received_value).__name__
    
    # Create base error response
    error_response = {
        "status": "error",
        "error_code": f"INVALID_{param_name.upper()}_TYPE",
        "message": f"Invalid type for {param_name} parameter",
        "details": {
            "received_type": received_type,
            "expected_types": expected_types,
            "received_value": str(received_value),
            "parameter": param_name
        }
    }
    
    # Add validation error details if provided
    if validation_error:
        error_response["details"]["validation_error"] = validation_error
    
    # Add context ID if provided
    if context_id:
        error_response["details"]["context_id"] = context_id
    
    # Log the validation error for debugging
    log_message = (
        f"Validation error for parameter '{param_name}': "
        f"expected {' or '.join(expected_types)}, "
        f"received {received_type} with value: {received_value}"
    )
    if context_id:
        log_message += f" (context_id: {context_id})"
    if validation_error:
        log_message += f" - {validation_error}"
    
    logger.error(log_message)
    
    return error_response


def create_generic_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    log_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized generic error response.
    
    Args:
        error_code: Specific error code for the error type
        message: Human-readable error message
        details: Optional dictionary with additional error details
        log_message: Optional custom log message (defaults to the error message)
        
    Returns:
        Dictionary with standardized error response format
    """
    error_response = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {}
    }
    
    # Log the error for debugging
    logger.error(log_message or message)
    
    return error_response


def validate_and_normalize_tags(tags: Any) -> Optional[List[str]]:
    """
    Validate and normalize tags parameter to handle various input formats.
    
    Args:
        tags: Input tags parameter of any type
        
    Returns:
        Optional[List[str]]: Normalized tags as None or list of strings
        
    Raises:
        ValueError: If tags parameter has invalid type or content
    """
    logger.debug(f"Starting tags validation - received type: {type(tags).__name__}, value: {repr(tags)}")
    
    # Handle None case - convert to empty list (clears tags)
    if tags is None:
        logger.debug("Tags parameter is None, normalizing to empty list for tag clearing")
        logger.info("Tags successfully processed: None input normalized to empty list")
        return []
    
    # Handle string case - convert to single-item list
    if isinstance(tags, str):
        logger.debug(f"Converting single string tag '{tags}' to list format")
        normalized_result = [tags]
        logger.info(f"Tags successfully processed: string '{tags}' converted to list with 1 item")
        return normalized_result
    
    # Handle list case
    if isinstance(tags, list):
        # Handle empty list
        if not tags:
            logger.debug("Tags parameter is empty list, maintaining empty list format")
            logger.info("Tags successfully processed: empty list maintained")
            return []
        
        logger.debug(f"Validating list with {len(tags)} items: {tags}")
        
        # Validate all items in list are strings
        non_string_items = []
        for i, item in enumerate(tags):
            if not isinstance(item, str):
                non_string_items.append(f"index {i}: {type(item).__name__} ({repr(item)})")
        
        if non_string_items:
            error_msg = f"All items in tags list must be strings. Found non-string items: {', '.join(non_string_items)}"
            logger.error(f"Tags validation failed - mixed types in list. Original input: {repr(tags)}. Non-string items: {', '.join(non_string_items)}")
            raise ValueError(error_msg)
        
        logger.debug(f"All {len(tags)} items in tags list validated as strings")
        logger.info(f"Tags successfully processed: list with {len(tags)} valid string items")
        return tags
    
    # Handle invalid types
    received_type = type(tags).__name__
    error_msg = f"Invalid type for tags parameter. Expected None, string, or list of strings, but received {received_type}"
    logger.error(f"Tags validation failed - invalid type. Expected: [None, str, list], received: {received_type}, value: {repr(tags)}")
    raise ValueError(error_msg)


@mcp.tool
def store_context(
    data: str, 
    title: Optional[str] = None, 
    tags: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Store context data with compression and metadata.
    
    Args:
        data: Context data to store (required)
        title: Optional title for the context
        tags: Optional tags for categorization (string or list of strings)
        
    Returns:
        Dictionary with context ID, status, and compression info
    """
    try:
        # Validate and normalize tags parameter
        try:
            logger.debug(f"store_context: Starting tags validation for input: {repr(tags)}")
            normalized_tags = validate_and_normalize_tags(tags)
            logger.info(f"store_context: Tags validation successful - normalized to {len(normalized_tags) if normalized_tags else 0} items")
        except ValueError as e:
            logger.error(f"store_context: Tags validation failed for input {repr(tags)} - {str(e)}")
            return create_validation_error_response(
                param_name="tags",
                received_value=tags,
                expected_types=["None", "list of strings", "string"],
                validation_error=str(e)
            )
        
        # Validate input
        if not data or not data.strip():
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Context data cannot be empty",
                details={"parameter": "data"}
            )
        
        # Store the context with normalized tags
        logger.debug(f"store_context: Storing context with title='{title}', tags={normalized_tags}, data_length={len(data)}")
        context_id = context_manager.store_context(data, title, normalized_tags)
        
        # Get compression info for response
        context_info = context_manager.get_context_summary(context_id)
        metadata = context_info['metadata']
        
        # Calculate compression ratio
        compression_ratio = metadata['compressed_size'] / metadata['original_size'] if metadata['original_size'] > 0 else 1.0
        
        logger.info(f"store_context: Successfully stored context '{context_id}' with {len(normalized_tags) if normalized_tags else 0} tags, compression ratio: {round(compression_ratio, 3)}")
        
        return {
            "status": "success",
            "id": context_id,
            "original_size": metadata['original_size'],
            "compressed_size": metadata['compressed_size'],
            "compression_ratio": round(compression_ratio, 3),
            "compression_method": metadata['compression_method']
        }
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            log_message=f"Validation error in store_context: {e}"
        )
    except Exception as e:
        return create_generic_error_response(
            error_code="STORAGE_ERROR",
            message=f"Failed to store context: {str(e)}",
            log_message=f"Error in store_context: {e}"
        )


@mcp.tool
def retrieve_context(context_id: str) -> Dict[str, Any]:
    """
    Retrieve and decompress context data by ID.
    
    Args:
        context_id: Unique context identifier
        
    Returns:
        Dictionary with context data and metadata, or error information
    """
    try:
        # Validate input
        if not context_id or not context_id.strip():
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Context ID cannot be empty",
                details={"parameter": "context_id"}
            )
        
        # Retrieve the context
        context_data = context_manager.retrieve_context(context_id.strip())
        
        return {
            "status": "success",
            **context_data
        }
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            log_message=f"Validation error in retrieve_context: {e}"
        )
    except RuntimeError as e:
        if "not found" in str(e).lower():
            return create_generic_error_response(
                error_code="CONTEXT_NOT_FOUND",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in retrieve_context: {e}"
            )
        else:
            return create_generic_error_response(
                error_code="RETRIEVAL_ERROR",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in retrieve_context: {e}"
            )
    except Exception as e:
        return create_generic_error_response(
            error_code="INTERNAL_ERROR",
            message=f"An unexpected error occurred: {str(e)}",
            details={"context_id": context_id},
            log_message=f"Unexpected error in retrieve_context: {e}"
        )


@mcp.tool
def search_contexts(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search for contexts matching the query.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary with search results or error information
    """
    try:
        # Validate input
        if not query or not query.strip():
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Search query cannot be empty",
                details={"parameter": "query"}
            )
        
        if limit <= 0 or limit > 100:
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Limit must be between 1 and 100",
                details={"limit": limit, "parameter": "limit"}
            )
        
        # Search contexts
        results = context_manager.search_contexts(query.strip(), limit=limit)
        
        return {
            "status": "success",
            "query": query.strip(),
            "results": results,
            "count": len(results)
        }
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            details={"query": query, "limit": limit},
            log_message=f"Validation error in search_contexts: {e}"
        )
    except Exception as e:
        return create_generic_error_response(
            error_code="SEARCH_ERROR",
            message=f"Failed to search contexts: {str(e)}",
            details={"query": query, "limit": limit},
            log_message=f"Error in search_contexts: {e}"
        )


@mcp.tool
def list_contexts(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    List contexts with pagination support.
    
    Args:
        limit: Maximum number of results to return (default: 50, max: 100)
        offset: Number of results to skip (default: 0)
        
    Returns:
        Dictionary with context list or error information
    """
    try:
        # Validate input
        if limit <= 0 or limit > 100:
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Limit must be between 1 and 100",
                details={"limit": limit, "parameter": "limit"}
            )
        
        if offset < 0:
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Offset cannot be negative",
                details={"offset": offset, "parameter": "offset"}
            )
        
        # List contexts
        results = context_manager.list_contexts(limit=limit, offset=offset)
        
        return {
            "status": "success",
            "results": results,
            "count": len(results),
            "pagination": {
                "limit": limit,
                "offset": offset
            }
        }
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            details={"limit": limit, "offset": offset},
            log_message=f"Validation error in list_contexts: {e}"
        )
    except Exception as e:
        return create_generic_error_response(
            error_code="LIST_ERROR",
            message=f"Failed to list contexts: {str(e)}",
            details={"limit": limit, "offset": offset},
            log_message=f"Error in list_contexts: {e}"
        )


@mcp.tool
def delete_context(context_id: str) -> Dict[str, Any]:
    """
    Delete a context by ID.
    
    Args:
        context_id: Unique context identifier
        
    Returns:
        Dictionary with deletion status or error information
    """
    try:
        # Validate input
        if not context_id or not context_id.strip():
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Context ID cannot be empty",
                details={"parameter": "context_id"}
            )
        
        # Delete the context
        success = context_manager.delete_context(context_id.strip())
        
        if success:
            return {
                "status": "success",
                "message": f"Context '{context_id}' deleted successfully",
                "context_id": context_id.strip()
            }
        else:
            return create_generic_error_response(
                error_code="DELETION_ERROR",
                message=f"Failed to delete context '{context_id}'",
                details={"context_id": context_id}
            )
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            details={"context_id": context_id},
            log_message=f"Validation error in delete_context: {e}"
        )
    except RuntimeError as e:
        if "not found" in str(e).lower():
            return create_generic_error_response(
                error_code="CONTEXT_NOT_FOUND",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in delete_context: {e}"
            )
        else:
            return create_generic_error_response(
                error_code="DELETION_ERROR",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in delete_context: {e}"
            )
    except Exception as e:
        return create_generic_error_response(
            error_code="INTERNAL_ERROR",
            message=f"An unexpected error occurred: {str(e)}",
            details={"context_id": context_id},
            log_message=f"Unexpected error in delete_context: {e}"
        )


@mcp.tool
def update_context(
    context_id: str,
    data: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Update an existing context.
    
    Args:
        context_id: Unique context identifier
        data: New context data (if provided, will be recompressed)
        title: New title (if provided)
        tags: New tags for categorization (string or list of strings, if provided)
        
    Returns:
        Dictionary with update status or error information
    """
    try:
        # Validate input
        if not context_id or not context_id.strip():
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Context ID cannot be empty",
                details={"parameter": "context_id"}
            )
        
        # For MCP tools, parameters are always provided, so we need to check if there's
        # actually something to update. We allow tags=None as a valid update (clears tags).
        # The validation will be done in the context_manager layer.
        
        if data is not None and (not data or not data.strip()):
            return create_generic_error_response(
                error_code="INVALID_INPUT",
                message="Context data cannot be empty when provided",
                details={"context_id": context_id, "parameter": "data"}
            )
        
        # Validate and normalize tags parameter (always process in MCP context)
        # Note: In MCP tools, parameters are always provided, so tags=None means "clear tags"
        try:
            logger.debug(f"update_context: Starting tags validation for context_id '{context_id.strip()}', input: {repr(tags)}")
            normalized_tags = validate_and_normalize_tags(tags)
            tags_was_processed = True
            logger.info(f"update_context: Tags validation successful for context_id '{context_id.strip()}' - normalized to {len(normalized_tags) if normalized_tags else 0} items")
        except ValueError as e:
            logger.error(f"update_context: Tags validation failed for context_id '{context_id.strip()}', input {repr(tags)} - {str(e)}")
            return create_validation_error_response(
                param_name="tags",
                received_value=tags,
                expected_types=["None", "list of strings", "string"],
                validation_error=str(e),
                context_id=context_id.strip()
            )
        
        # Update the context
        logger.debug(f"update_context: Updating context '{context_id.strip()}' with data={data is not None}, title={title is not None}, tags={normalized_tags}")
        success = context_manager.update_context(
            context_id.strip(),
            data=data,
            title=title,
            tags=normalized_tags
        )
        
        if success:
            # Get updated context summary for response
            updated_context = context_manager.get_context_summary(context_id.strip())
            
            logger.info(f"update_context: Successfully updated context '{context_id.strip()}' - data_updated={data is not None}, title_updated={title is not None}, tags_updated={tags_was_processed}, final_tags_count={len(normalized_tags) if normalized_tags else 0}")
            
            response = {
                "status": "success",
                "message": f"Context '{context_id}' updated successfully",
                "context_id": context_id.strip(),
                "updated_fields": {
                    "data": data is not None,
                    "title": title is not None,
                    "tags": tags_was_processed
                },
                "metadata": updated_context['metadata']
            }
            
            # Include tags information in response when tags were updated
            if tags is not None:
                response["tags_info"] = {
                    "original_tags_input": str(tags),
                    "normalized_tags": normalized_tags,
                    "tags_count": len(normalized_tags) if normalized_tags else 0
                }
            
            return response
        else:
            return create_generic_error_response(
                error_code="UPDATE_ERROR",
                message=f"Failed to update context '{context_id}'",
                details={"context_id": context_id}
            )
        
    except ValueError as e:
        return create_generic_error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            details={"context_id": context_id},
            log_message=f"Validation error in update_context: {e}"
        )
    except RuntimeError as e:
        if "not found" in str(e).lower():
            return create_generic_error_response(
                error_code="CONTEXT_NOT_FOUND",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in update_context: {e}"
            )
        else:
            return create_generic_error_response(
                error_code="UPDATE_ERROR",
                message=str(e),
                details={"context_id": context_id},
                log_message=f"Runtime error in update_context: {e}"
            )
    except Exception as e:
        return create_generic_error_response(
            error_code="INTERNAL_ERROR",
            message=f"An unexpected error occurred: {str(e)}",
            details={"context_id": context_id},
            log_message=f"Unexpected error in update_context: {e}"
        )


def main():
    """Main entry point for the MCP server."""
    try:
        mcp.run()
    finally:
        # Cleanup context manager on shutdown
        context_manager.close()


if __name__ == "__main__":
    main()
