from keel.security.scanning import FileSecurityValidator

# FileSecurityValidator checks extension allowlist (KEEL_ALLOWED_UPLOAD_EXTENSIONS),
# file size (KEEL_MAX_UPLOAD_SIZE), and malware via ClamAV magic-byte scanning.
# Both document and image uploads must pass through it so that size-bomb and
# polyglot-file attacks are blocked regardless of extension.
# (Previously validate_image_file only used FileExtensionValidator which skips the
# size cap and ClamAV scan — CVE-class: unauthenticated file-bomb / polyglot upload.)
validate_document_file = FileSecurityValidator()
validate_image_file = FileSecurityValidator()
