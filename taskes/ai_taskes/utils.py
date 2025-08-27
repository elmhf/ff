import os
import logging
import numpy as np
import nibabel as nib
from tensorflow.keras.models import load_model as keras_load_model
from datetime import datetime

# ===== Logger =====
logger = logging.getLogger(__name__)

# ===== Directories =====
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# تأكد الي الـ folders موجودين
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# ===== Helpers =====
def get_timestamp():
    """Generate timestamp string for unique filenames"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def load_model(model_name):
    """
    Load AI model (Keras/TensorFlow).
    model_name: اسم الموديل (ex: 'tooth_segmentation')
    """
    model_path = os.path.join(MODELS_DIR, f"{model_name}.h5")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"❌ Model not found: {model_path}")

    logger.info(f"📥 Loading model: {model_path}")
    return keras_load_model(model_path)

def save_output(prediction, upload_id):
    """
    Save AI model output (3D numpy array) as NIfTI file.
    Returns path of saved file.
    """
    if not isinstance(prediction, np.ndarray):
        raise ValueError("Prediction must be a numpy array")

    # Save as NIfTI
    nifti_img = nib.Nifti1Image(prediction.astype(np.float32), affine=np.eye(4))
    result_filename = f"{upload_id}_{get_timestamp()}_result.nii.gz"
    result_path = os.path.join(RESULTS_DIR, result_filename)

    nib.save(nifti_img, result_path)
    logger.info(f"✅ Result saved: {result_path}")

    return result_path

def save_json_report(report_data, upload_id):
    """
    Save analysis results in JSON format
    """
    import json
    result_filename = f"{upload_id}_{get_timestamp()}_report.json"
    result_path = os.path.join(RESULTS_DIR, result_filename)

    with open(result_path, "w") as f:
        json.dump(report_data, f, indent=4)

    logger.info(f"📝 Report saved: {result_path}")
    return result_path

def normalize_array(data):
    """
    Normalize numpy array [0,1]
    """
    data = data.astype(np.float32)
    return (data - np.min(data)) / (np.max(data) - np.min(data) + 1e-8)

def load_nifti(file_path):
    """
    Load NIfTI file and return numpy array
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    img = nib.load(file_path)
    return img.get_fdata(), img.affine
