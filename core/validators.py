from django.core.validators import FileExtensionValidator

# Allowed extensions for document uploads
DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'rtf', 'odt', 'ods']
IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']

validate_document_file = FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS)
validate_image_file = FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS)
