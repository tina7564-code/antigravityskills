import asyncio
import smtplib
from email.mime.text import MIMEText

import httpx

from app.config import get_settings


class AlertSystem:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send_high_risk_alert(self, title: str, body: str) -> None:
        tasks = []
        if self.settings.alert_email_to and self.settings.smtp_host:
            tasks.append(self._send_email(title, body))
        if self.settings.wecom_webhook_url:
            tasks.append(self._send_wecom(body))
        if tasks:
            await asyncio.gather(*tasks)

    async def _send_email(self, title: str, body: str) -> None:
        message = MIMEText(body, _charset='utf-8')
        message['Subject'] = title
        message['From'] = self.settings.smtp_username or 'monitor@example.com'
        message['To'] = self.settings.alert_email_to or ''

        def _send() -> None:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.starttls()
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)

        await asyncio.to_thread(_send)

    async def _send_wecom(self, body: str) -> None:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                self.settings.wecom_webhook_url,
                json={'msgtype': 'text', 'text': {'content': body}},
            )
