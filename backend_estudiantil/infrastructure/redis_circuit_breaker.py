"""
backend_estudiantil/infrastructure/redis_circuit_breaker.py
------------------------------------------------------------
Implementación de Circuit Breaker para Redis con tiempos de espera cortos
y enfriamiento (cooldown) de 30 segundos tras fallo de conexión o comando.
Garantiza que la API degrade elegantemente a memoria local sin retrasos de red (0 ms).
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RedisCircuitBreaker:
    """Controlador de corte temporal (circuit breaker) para Redis.

    Estados:
    - CERRADO (Operación normal): Se intenta comunicar con Redis usando timeouts cortos (< 1s).
    - ABIERTO (En fallo / Cooldown): Durante 30 segundos después de un fallo, no se intenta
      contactar a Redis; las operaciones caen de forma inmediata a memoria local (0 ms).
    """

    def __init__(self, cooldown_seconds: float = 30.0, timeout_seconds: float = 0.5):
        self.cooldown_seconds = cooldown_seconds
        self.timeout_seconds = timeout_seconds
        self.last_failure_time: float = 0.0

    @property
    def is_open(self) -> bool:
        """Retorna True si el circuito está ABIERTO (en periodo de enfriamiento tras fallo)."""
        if self.last_failure_time <= 0:
            return False
        elapsed = time.time() - self.last_failure_time
        return elapsed < self.cooldown_seconds

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Registra una falla de conexión u operación, abriendo el circuito."""
        self.last_failure_time = time.time()
        logger.warning(
            "Fallo de comunicación con Redis (%s). Circuito ABIERTO por %.1f segundos; usando memoria local.",
            error or "error no especificado",
            self.cooldown_seconds,
        )

    def record_success(self) -> None:
        """Registra una respuesta exitosa, cerrando el circuito."""
        self.last_failure_time = 0.0

    def reset(self) -> None:
        """Restablece el estado del circuito para pruebas o reconexión forzada."""
        self.last_failure_time = 0.0


# Instancias compartidas por subsistema
chat_redis_circuit_breaker = RedisCircuitBreaker(cooldown_seconds=30.0, timeout_seconds=0.5)
login_redis_circuit_breaker = RedisCircuitBreaker(cooldown_seconds=30.0, timeout_seconds=0.5)
confirmation_redis_circuit_breaker = RedisCircuitBreaker(cooldown_seconds=30.0, timeout_seconds=0.5)
slowapi_redis_circuit_breaker = RedisCircuitBreaker(cooldown_seconds=30.0, timeout_seconds=0.5)
