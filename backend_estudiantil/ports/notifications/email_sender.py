from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Puerto para el servicio de envío de notificaciones por correo electrónico."""

    @abstractmethod
    async def send_verification_code(
        self,
        to_email: str,
        code: str,
        verification_link: str | None = None,
    ) -> bool:
        """Envía el código o enlace de confirmación al correo institucional."""
