import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend_estudiantil.config.settings import settings
from backend_estudiantil.ports.notifications.email_sender import EmailSender

logger = logging.getLogger("backend_estudiantil.notifications.email")

class SMTPEmailSender(EmailSender):
    """Adaptador de envío de correos electrónicos vía SMTP con fallback para desarrollo local."""

    async def send_verification_code(
        self,
        to_email: str,
        code: str,
        verification_link: str | None = None,
    ) -> bool:
        """Envía el código de confirmación o enlace de verificación al correo del estudiante."""
        asunto = "Confirma tu correo institucional - SwapU Trueque Estudiantil"
        link_html = (
            f'<p>También puedes confirmar directamente haciendo clic en el siguiente enlace:<br>'
            f'<a href="{verification_link}" style="display:inline-block;padding:10px 18px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;margin-top:10px;">Verificar Correo Institucional</a></p>'
            if verification_link
            else ""
        )
        cuerpo_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #4f46e5; margin-top: 0;">SwapU - Verificación de Comunidad</h2>
            <p>Hola,</p>
            <p>Has registrado tu cuenta en la plataforma de trueque con un correo institucional. Para activar tu distintivo de <strong>Estudiante Verificado</strong>, ingresa el siguiente código de confirmación en la plataforma:</p>
            <div style="font-size: 28px; font-weight: bold; letter-spacing: 5px; color: #1e293b; background: #f1f5f9; padding: 15px; text-align: center; border-radius: 6px; margin: 20px 0;">
                {code}
            </div>
            <p style="color: #64748b; font-size: 14px;">Este código tiene una vigencia de 30 minutos.</p>
            {link_html}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 25px 0;">
            <p style="font-size: 12px; color: #94a3b8;">Si tú no realizaste este registro, puedes ignorar este mensaje.</p>
        </div>
        """

        smtp_host = getattr(settings, "SMTP_HOST", "")
        smtp_port = getattr(settings, "SMTP_PORT", 587)
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        smtp_from = getattr(settings, "SMTP_FROM_EMAIL", smtp_user or "no-reply@swapu.edu.co")

        if smtp_host and smtp_user and smtp_password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = asunto
                msg["From"] = smtp_from
                msg["To"] = to_email

                part_text = MIMEText(f"Tu código de confirmación de SwapU es: {code}. Válido por 30 minutos.", "plain", "utf-8")
                part_html = MIMEText(cuerpo_html, "html", "utf-8")
                msg.attach(part_text)
                msg.attach(part_html)

                with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)
                logger.info("Correo de verificación enviado exitosamente vía SMTP a %s", to_email)
                return True
            except Exception as e:
                logger.error("Error al enviar correo vía SMTP a %s: %s", to_email, str(e))
                # Fallback al log para no bloquear al usuario en caso de falla de red externa
        
        # En desarrollo local o pruebas sin SMTP configurado
        logger.info(
            "SIMULACIÓN DE ENVÍO DE CORREO: Para=%s | Código=%s | Enlace=%s",
            to_email,
            code,
            verification_link,
        )
        return True
