import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')


class NonRetryableError(Exception):
    """Base class for errors that should not be retried by retry decorators."""
    pass

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator for async functions with exponential backoff.
    
    Args:
        retries: Maximum number of retries
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        break
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

def async_retry_unless_not_found(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator for async functions with exponential backoff, but skips retries for VMNotFoundError.
    """
    from ..vm.models import VMNotFoundError

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    # Skip retries for known non-retryable cases
                    if isinstance(e, (VMNotFoundError, NonRetryableError)):
                        raise e

                    last_exception = e
                    if attempt == retries:
                        break
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator
