# File: app/common/email_utils.py

import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader, Template

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending various types of emails."""
    
    def __init__(self):
        self.smtp_server = settings.EMAIL_HOST
        self.smtp_port = settings.EMAIL_PORT
        self.username = settings.EMAIL_USER
        self.password = settings.EMAIL_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.use_tls = settings.EMAIL_USE_TLS
        
        # Setup Jinja2 environment for templates
        template_dir = Path("app/templates")
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)) if template_dir.exists() else None,
            autoescape=True
        )
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """Send email with HTML and optional text body."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to_emails)
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Add text part
            if text_body:
                text_part = MIMEText(text_body, 'plain')
                msg.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    await self._add_attachment(msg, file_path)
            
            # Send email
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                server.send_message(msg, to_addrs=all_recipients)
            
            logger.info(f"Email sent successfully to {len(all_recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """Add file attachment to email."""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Attachment file not found: {file_path}")
                return
            
            with open(path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {path.name}'
            )
            
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Failed to add attachment {file_path}: {e}")
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render email template with context."""
        try:
            if self.jinja_env:
                template = self.jinja_env.get_template(template_name)
                return template.render(**context)
            else:
                # Fallback to simple string replacement
                return self._simple_template_render(template_name, context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            return ""
    
    def _simple_template_render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Simple template rendering fallback."""
        # Basic template content for fallback
        templates = {
            "welcome_email.html": """
            <h1>Welcome to FastAPIVerseHub!</h1>
            <p>Hello {name},</p>
            <p>Thank you for joining our platform. We're excited to have you on board!</p>
            <p>Best regards,<br>The FastAPIVerseHub Team</p>
            """,
            "reset_password.html": """
            <h1>Password Reset Request</h1>
            <p>Hello {name},</p>
            <p>You requested to reset your password. Click the link below:</p>
            <p><a href="{reset_link}">Reset Password</a></p>
            <p>This link expires in 15 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            """
        }
        
        template_content = templates.get(template_name, "")
        for key, value in context.items():
            template_content = template_content.replace(f"{{{key}}}", str(value))
        
        return template_content
    
    async def send_welcome_email(self, email: str, name: Optional[str] = None) -> bool:
        """Send welcome email to new user."""
        context = {
            "name": name or email.split("@")[0],
            "email": email,
            "app_name": settings.APP_NAME,
            "current_year": datetime.now().year
        }
        
        html_body = self._render_template("welcome_email.html", context)
        text_body = f"""
        Welcome to {settings.APP_NAME}!
        
        Hello {context['name']},
        
        Thank you for joining our platform. We're excited to have you on board!
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        return await self.send_email(
            to_emails=[email],
            subject=f"Welcome to {settings.APP_NAME}!",
            html_body=html_body,
            text_body=text_body
        )
    
    async def send_password_reset_email(
        self, 
        email: str, 
        reset_token: str, 
        name: Optional[str] = None
    ) -> bool:
        """Send password reset email."""
        reset_link = f"https://example.com/reset-password?token={reset_token}"
        
        context = {
            "name": name or email.split("@")[0],
            "email": email,
            "reset_link": reset_link,
            "app_name": settings.APP_NAME,
            "expiry_minutes": 15
        }
        
        html_body = self._render_template("reset_password.html", context)
        text_body = f"""
        Password Reset Request
        
        Hello {context['name']},
        
        You requested to reset your password. Click the link below:
        {reset_link}
        
        This link expires in 15 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        return await self.send_email(
            to_emails=[email],
            subject="Password Reset Request",
            html_body=html_body,
            text_body=text_body
        )
    
    async def send_magic_link_email(self, email: str, magic_link: str) -> bool:
        """Send magic link for passwordless authentication."""
        context = {
            "email": email,
            "magic_link": magic_link,
            "app_name": settings.APP_NAME,
            "expiry_minutes": 15
        }
        
        html_body = f"""
        <h1>Your Magic Login Link</h1>
        <p>Hello,</p>
        <p>Click the link below to sign in to {settings.APP_NAME}:</p>
        <p><a href="{magic_link}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Sign In</a></p>
        <p>This link expires in 15 minutes and can only be used once.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        
        text_body = f"""
        Your Magic Login Link
        
        Hello,
        
        Click the link below to sign in to {settings.APP_NAME}:
        {magic_link}
        
        This link expires in 15 minutes and can only be used once.
        
        If you didn't request this, please ignore this email.
        """
        
        return await self.send_email(
            to_emails=[email],
            subject=f"Sign in to {settings.APP_NAME}",
            html_body=html_body,
            text_body=text_body
        )
    
    async def send_course_enrollment_confirmation(
        self,
        email: str,
        course_title: str,
        instructor_name: str,
        name: Optional[str] = None
    ) -> bool:
        """Send course enrollment confirmation."""
        context = {
            "name": name or email.split("@")[0],
            "course_title": course_title,
            "instructor_name": instructor_name,
            "app_name": settings.APP_NAME
        }
        
        html_body = f"""
        <h1>Course Enrollment Confirmation</h1>
        <p>Hello {context['name']},</p>
        <p>You have successfully enrolled in:</p>
        <h2>{course_title}</h2>
        <p>Instructor: {instructor_name}</p>
        <p>You can start learning immediately by visiting your dashboard.</p>
        <p>Happy learning!</p>
        """
        
        return await self.send_email(
            to_emails=[email],
            subject=f"Enrolled in {course_title}",
            html_body=html_body
        )
    
    async def send_course_completion_certificate(
        self,
        email: str,
        course_title: str,
        certificate_url: str,
        name: Optional[str] = None
    ) -> bool:
        """Send course completion certificate."""
        html_body = f"""
        <h1>Congratulations! Course Completed</h1>
        <p>Hello {name or email.split("@")[0]},</p>
        <p>Congratulations on completing the course:</p>
        <h2>{course_title}</h2>
        <p>Your certificate is ready for download:</p>
        <p><a href="{certificate_url}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Download Certificate</a></p>
        <p>Well done on your learning achievement!</p>
        """
        
        return await self.send_email(
            to_emails=[email],
            subject=f"Certificate for {course_title}",
            html_body=html_body
        )
    
    async def send_notification_email(
        self,
        email: str,
        subject: str,
        message: str,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None
    ) -> bool:
        """Send general notification email."""
        html_body = f"""
        <h1>{subject}</h1>
        <p>{message}</p>
        """
        
        if action_url and action_text:
            html_body += f"""
            <p><a href="{action_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{action_text}</a></p>
            """
        
        return await self.send_email(
            to_emails=[email],
            subject=subject,
            html_body=html_body
        )
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        batch_size: int = 50
    ) -> Dict[str, int]:
        """Send bulk emails in batches."""
        total_sent = 0
        total_failed = 0
        
        # Send in batches to avoid overwhelming SMTP server
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            try:
                success = await self.send_email(
                    to_emails=batch,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body
                )
                
                if success:
                    total_sent += len(batch)
                else:
                    total_failed += len(batch)
                    
            except Exception as e:
                logger.error(f"Failed to send bulk email batch: {e}")
                total_failed += len(batch)
        
        return {
            "total_sent": total_sent,
            "total_failed": total_failed,
            "total_recipients": len(recipients)
        }
    
    def validate_email(self, email: str) -> bool:
        """Basic email validation."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    async def test_connection(self) -> bool:
        """Test SMTP connection."""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                return True
                
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False