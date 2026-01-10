"""Resume handling and attachment functionality."""
from pathlib import Path
from typing import Optional
import base64

from observability.logger import get_logger
import config


logger = get_logger(__name__)


class ResumeHandler:
    """Handle resume PDF for email attachments."""
    
    def __init__(self, resume_path: Optional[str] = None):
        self.resume_path = Path(resume_path or config.YOUR_RESUME) if resume_path or config.YOUR_RESUME else None
        
        if self.resume_path and not self.resume_path.exists():
            logger.warning(f"Resume file not found: {self.resume_path}")
            self.resume_path = None
        elif self.resume_path:
            logger.info(f"Resume loaded: {self.resume_path}")
    
    def has_resume(self) -> bool:
        """Check if resume is available."""
        return self.resume_path is not None and self.resume_path.exists()
    
    def get_resume_bytes(self) -> Optional[bytes]:
        """Get resume file as bytes for email attachment."""
        if not self.has_resume():
            return None
        
        try:
            with open(self.resume_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read resume: {e}")
            return None
    
    def get_resume_filename(self) -> str:
        """Get resume filename."""
        if not self.has_resume():
            return "resume.pdf"
        return self.resume_path.name
    
    def attach_to_email(self, msg) -> None:
        """Attach resume to email message."""
        if not self.has_resume():
            return
        
        try:
            from email.mime.application import MIMEApplication
            
            resume_bytes = self.get_resume_bytes()
            if not resume_bytes:
                return
            
            attachment = MIMEApplication(resume_bytes, _subtype="pdf")
            attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=self.get_resume_filename()
            )
            msg.attach(attachment)
            
            logger.debug(f"Attached resume: {self.get_resume_filename()}")
            
        except Exception as e:
            logger.error(f"Failed to attach resume: {e}")
