from celery import shared_task
import nibabel as nib
import numpy as np
import os
from .utils import normalize_array
import logging

logger = logging.getLogger(__name__)

@shared_task
def preprocess_file(file_path, upload_id):
    """
    Preprocess medical file before AI model.
    - Load NIfTI
    - Normalize intensities
    - Return path of preprocessed file
    """
    logger.info(f"🔄 Preprocessing file: {file_path}")

    # Load file
    img = nib.load(file_path)
    data = img.get_fdata()

    # Normalize
    norm_data = normalize_array(data)

    # Save new file
    preprocessed_path = file_path.replace(".nii", "_preprocessed.nii")
    new_img = nib.Nifti1Image(norm_data, img.affine)
    nib.save(new_img, preprocessed_path)

    logger.info(f"✅ Preprocessed file saved: {preprocessed_path}")
    return {"upload_id": upload_id, "file_path": preprocessed_path}
