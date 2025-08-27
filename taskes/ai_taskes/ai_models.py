from time import sleep
from celery import shared_task
import nibabel as nib
import numpy as np
from .utils import load_model, save_output

@shared_task
def run_segmentation(file_path, upload_id):
    """Run AI segmentation on NIfTI file"""
    # # 1. Load NIfTI
    # img = nib.load(file_path)
    # data = img.get_fdata()
    sleep(1000)  # Simulate processing time
    # # 2. Load AI model
    # model = load_model("tooth_segmentation")

    # # 3. Predict
    # prediction = model.predict(data)

    # # 4. Save results
    result_path=0
    # result_path = save_output(prediction, upload_id)

    return {"upload_id": upload_id, "result_path": result_path}
