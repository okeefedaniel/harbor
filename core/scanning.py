"""
File scanning utilities for uploaded documents.

Validates file extensions and size, and optionally scans for malware
via ClamAV when ``CLAMAV_ENABLED=True`` and the ``pyclamd`` package is
installed.
"""
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

class ScanResult:
    def __init__(self, is_clean=True, message=''):
        self.is_clean = is_clean
        self.message = message

def scan_file(file_obj):
    """Scan an uploaded file for malware.

    Args:
        file_obj: Django UploadedFile or file-like object

    Returns:
        ScanResult with is_clean boolean and message
    """
    filename = getattr(file_obj, 'name', 'unknown')
    file_size = getattr(file_obj, 'size', 0)

    logger.info(f"Scanning file: {filename} ({file_size} bytes)")

    # Check file extension
    _, ext = os.path.splitext(filename.lower())
    allowed = getattr(settings, 'ALLOWED_UPLOAD_EXTENSIONS', [])
    if allowed and ext not in allowed:
        return ScanResult(
            is_clean=False,
            message=f"File type '{ext}' is not allowed. Permitted: {', '.join(allowed)}"
        )

    # Check file size (10MB default)
    max_size = getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
    if file_size > max_size:
        return ScanResult(
            is_clean=False,
            message=f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)"
        )

    # ClamAV malware scanning (opt-in via settings)
    if getattr(settings, 'CLAMAV_ENABLED', False):
        try:
            import pyclamd
            socket_path = getattr(
                settings, 'CLAMAV_SOCKET', '/var/run/clamav/clamd.ctl')
            cd = pyclamd.ClamdUnixSocket(filename=socket_path)
            cd.ping()
            file_obj.seek(0)
            result = cd.scan_stream(file_obj.read())
            file_obj.seek(0)
            if result:
                status = list(result.values())[0]
                return ScanResult(
                    is_clean=False,
                    message=f"Malware detected: {status}")
            logger.info(f"ClamAV scan clean: {filename}")
        except ImportError:
            logger.warning(
                'CLAMAV_ENABLED is True but pyclamd is not installed. '
                'Install it with: pip install pyclamd')
        except Exception as exc:
            logger.warning(
                'ClamAV scan failed for %s: %s — allowing upload (fail-open)',
                filename, exc)

    logger.info(f"File scan passed: {filename}")
    return ScanResult(is_clean=True, message='File scan passed')
