import os
import nibabel as nib
import pydicom
from flask import current_app


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    if filename.lower().endswith('.nii.gz'):
        return True
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in current_app.config['ALLOWED_EXTENSIONS']


def validate_file_content(file_path, filename):
    try:
        if filename.lower().endswith(('.nii', '.nii.gz')):
            img = nib.load(file_path)
            data = img.get_fdata()
            return (data.size > 0, "Valid NIfTI file") if data.size > 0 else (False, "Empty NIfTI file")
        elif filename.lower().endswith(('.dcm', '.dicom', '.ima')):
            ds = pydicom.dcmread(file_path)
            return (True, "Valid DICOM file") if hasattr(ds, 'pixel_array') else (False, "DICOM has no pixel data")
        return True, "File validation passed"
    except Exception as e:
        return False, f"File validation failed: {str(e)}"


