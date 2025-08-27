import os

def validate_file_content(file_path, filename):
    if not os.path.exists(file_path):
        return False, "File does not exist"
    if filename.lower().endswith(('.nii', '.nii.gz', '.dcm')):
        return True, "Valid file"
    return False, "Unsupported file type"
