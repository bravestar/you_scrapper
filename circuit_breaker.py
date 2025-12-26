"""
IYE Circuit Breaker & Retry Policy
Prevents retry storms and implements smart backoff strategies
"""
import asyncio
import time
import random
from typing import Callable, TypeVar, Optional, Set
from enum import Enum
from functools import wraps
from config import IYEConfig

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    Centralizes retry logic across all components.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = IYEConfig.CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: float = IYEConfig.CIRCUIT_BREAKER_TIMEOUT,
        recovery_threshold: int = IYEConfig.CIRCUIT_BREAKER_RECOVERY_THRESHOLD
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.recovery_threshold = recovery_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        
    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.recovery_threshold:
                self._close_circuit()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self._open_circuit()
        elif self.failure_count >= self.failure_threshold:
            self._open_circuit()
    
    def can_attempt(self) -> bool:
        """Check if request should be attempted"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._half_open_circuit()
                return True
            return False
        
        # HALF_OPEN state - allow single probe
        return True
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _open_circuit(self):
        """Open circuit - reject requests"""
        self.state = CircuitState.OPEN
        self.success_count = 0
        print(f"[Circuit Breaker: {self.name}] OPENED - rejecting requests")
    
    def _half_open_circuit(self):
        """Half-open - testing recovery"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        print(f"[Circuit Breaker: {self.name}] HALF-OPEN - testing recovery")
    
    def _close_circuit(self):
        """Close circuit - normal operation"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        print(f"[Circuit Breaker: {self.name}] CLOSED - normal operation resumed")

class RetryPolicy:
    """
    Intelligent retry with exponential backoff and jitter.
    Prevents thundering herd and respects circuit breakers.
    """
    
    # Retryable errors (transient network issues)
    RETRYABLE_ERRORS = {
        "timeout",
        "connection_reset",
        "connection_refused",
        "network_unreachable"
    }
    
    # Non-retryable status codes (permanent errors)
    TERMINAL_STATUS_CODES = {400, 401, 403, 404, 410}
    
    @staticmethod
    def is_retryable_error(exception: Exception, status_code: Optional[int] = None) -> bool:
        """Classify errors into retryable vs terminal"""
        if status_code:
            # 5xx errors are retryable, 4xx mostly aren't
            if status_code in RetryPolicy.TERMINAL_STATUS_CODES:
                return False
            if 500 <= status_code < 600:
                return True
        
        # Check exception type and message
        error_msg = str(exception).lower()
        return any(retryable in error_msg for retryable in RetryPolicy.RETRYABLE_ERRORS)
    
    @staticmethod
    def calculate_backoff(attempt: int, base: float = IYEConfig.RETRY_BACKOFF_BASE) -> float:
        """
        Calculate exponential backoff with jitter.
        Jitter prevents multiple clients retrying simultaneously.
        """
        exponential_delay = base ** attempt
        jitter = random.uniform(0, IYEConfig.RETRY_JITTER_MAX)
        return exponential_delay + jitter
    
    @staticmethod
    async def with_retry(
        func: Callable,
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_retries: int = IYEConfig.MAX_RETRIES,
        operation_name: str = "operation"
    ):
        """
        Execute function with retry logic and circuit breaker.
        
        Args:
            func: Async callable to execute
            circuit_breaker: Optional circuit breaker instance
            max_retries: Maximum retry attempts
            operation_name: Name for logging
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            # Check circuit breaker
            if circuit_breaker and not circuit_breaker.can_attempt():
                raise Exception(f"Circuit breaker OPEN for {operation_name}")
            
            try:
                result = await func()
                
                # Success - record in circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_success()
                
                return result
                
            except Exception as e:
                last_exception = e
                status_code = getattr(e, 'status_code', None)
                
                # Record failure in circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_failure()
                
                # Check if retryable
                if not RetryPolicy.is_retryable_error(e, status_code):
                    print(f"[Retry] {operation_name} - Terminal error, not retrying: {e}")
                    raise
                
                # Check if we have retries left
                if attempt >= max_retries:
                    print(f"[Retry] {operation_name} - Max retries exhausted")
                    raise
                
                # Calculate backoff and retry
                backoff = RetryPolicy.calculate_backoff(attempt)
                print(f"[Retry] {operation_name} - Attempt {attempt + 1}/{max_retries} failed. "
                      f"Retrying in {backoff:.2f}s... Error: {e}")
                await asyncio.sleep(backoff)
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception

def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator for automatic circuit breaker integration"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await RetryPolicy.with_retry(
                lambda: func(*args, **kwargs),
                circuit_breaker=circuit_breaker,
                operation_name=func.__name__
            )
        return wrapper
    return decorator
