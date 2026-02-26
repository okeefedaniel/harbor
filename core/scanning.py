"""
File scanning utilities for uploaded documents.

In production, this would integrate with ClamAV or a cloud-based
malware scanning service. The current implementation is a stub that
logs scan requests and validates file extensions.
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

    # TODO: Integrate ClamAV or cloud scanning service
    # Example ClamAV integration:
    # import pyclamd
    # cd = pyclamd.ClamdUnixSocket()
    # result = cd.scan_stream(file_obj.read())
    # file_obj.seek(0)  # Reset file pointer
    # if result:
    #     return ScanResult(is_clean=False, message=f"Malware detected: {result}")

    logger.info(f"File scan passed: {filename}")
    return ScanResult(is_clean=True, message='File scan passed')
