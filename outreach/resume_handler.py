"""Resume handling with PDF parsing for experience extraction."""
from pathlib import Path
from typing import Optional

from observability.logger import get_logger
import config


logger = get_logger(__name__)


class ResumeHandler:
    def __init__(self, resume_path: Optional[str] = None):
        self.resume_path: Optional[Path] = None
        path_str = resume_path or config.YOUR_RESUME
        if path_str:
            p = Path(path_str)
            if p.exists():
                self.resume_path = p
                logger.info(f"Resume loaded: {p}")
            else:
                logger.warning(f"Resume not found: {p}")

    def has_resume(self) -> bool:
        return self.resume_path is not None and self.resume_path.exists()

    def get_resume_bytes(self) -> Optional[bytes]:
        if not self.has_resume():
            return None
        try:
            return self.resume_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read resume: {e}")
            return None

    def get_resume_filename(self) -> str:
        return self.resume_path.name if self.has_resume() else "resume.pdf"

    def attach_to_email(self, msg) -> None:
        if not self.has_resume():
            return
        try:
            from email.mime.application import MIMEApplication
            data = self.get_resume_bytes()
            if not data:
                return
            attachment = MIMEApplication(data, _subtype="pdf")
            attachment.add_header("Content-Disposition", "attachment", filename=self.get_resume_filename())
            msg.attach(attachment)
            logger.debug(f"Attached resume: {self.get_resume_filename()}")
        except Exception as e:
            logger.error(f"Failed to attach resume: {e}")

    def extract_experience_text(self) -> str:
        if not self.has_resume():
            return ""
        try:
            import subprocess
            result = subprocess.run(
                ["pdftotext", str(self.resume_path), "-"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return result.stdout[:2000]
        except FileNotFoundError:
            logger.debug("pdftotext not available, skipping extraction")
        except Exception as e:
            logger.debug(f"PDF extraction failed: {e}")
        return ""
