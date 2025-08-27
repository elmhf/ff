from celery import shared_task
import numpy as np
import logging
from .utils import save_json_report

logger = logging.getLogger(__name__)

@shared_task
def generate_report(results_dict, upload_id, clinic_id, patient_id, report_type, report_id):
    """
    Generate final medical report after AI model.
    - results_dict contains result_path (from AI task)
    - Extract simple metrics (example: volume of segmentation)
    - Save report as JSON
    """
    logger.info(f"📝 Generating report for upload: {upload_id}")

    result_path = results_dict.get("result_path", None)
    if not result_path:
        raise ValueError("Missing result_path from AI task")

    # Dummy metrics (example)
    report_data = {
        "upload_id": upload_id,
        "clinic_id": clinic_id,
        "patient_id": patient_id,
        "report_type": report_type,
        "report_id": report_id,
        "result_path": result_path,
        "metrics": {
            "segmentation_volume": float(np.random.rand() * 1000), # placeholder
            "tooth_count": int(np.random.randint(28, 32))          # placeholder
        }
    }

    report_path = save_json_report(report_data, upload_id)
    logger.info(f"✅ Report generated: {report_path}")

    return {"upload_id": upload_id, "report_path": report_path}
