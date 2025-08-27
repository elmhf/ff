import os


def upload_report_to_storage(report_data, clinic_id, patient_id, report_type, report_id, logger, supabase):
    """
    Upload report data to Supabase by inserting JSON data directly into a table.
    Args:
        report_data: The JSON data (dict) to be uploaded
        clinic_id, patient_id, report_type, report_id: Identifiers
        logger: Logger instance
        supabase: Supabase client
    """
    print(" 6666666666666666666666666666666666666666 66  Uploading report data to Supabase...")  # Debugging line
    try:
        if not supabase:
            logger.error("Supabase client not available")
            return {"success": False, "error": "Supabase client not available"}
        
        if not report_data:
            logger.error("Report data is empty or None")
            return {"success": False, "error": "Report data is empty"}
        
        # Validate that report_data is a dictionary (parsed JSON)
        if not isinstance(report_data, dict):
            logger.error(f"Report data must be a dictionary, got {type(report_data)}")
            return {"success": False, "error": f"Invalid data type: {type(report_data)}"}
        
        logger.info(f"Uploading report data for patient_id: {patient_id}, report_id: {report_id}")
        
        # Insert the JSON data directly as a parameter to Supabase table
        try:
            response = supabase.table("report_ai_json").insert({
                "clinic_id": clinic_id,
                "patient_id": patient_id,
                "report_type": report_type,
                "report_id": report_id,
                "data": report_data  # Direct JSON data as parameter
            }).execute()
            
            logger.info(f"Report JSON successfully uploaded to Supabase table")
            logger.debug(f"Data keys uploaded: {list(report_data.keys())}")
            
            return {"success": True, "response": response.data if hasattr(response, 'data') else str(response)}
            
        except Exception as e:
            logger.error(f"Error inserting data to Supabase table: {e}")
            return {"success": False, "error": f"Database insertion error: {str(e)}"}
    
    except Exception as e:
        logger.error(f"Unexpected error uploading report data to Supabase: {e}")
        return {"success": False, "error": str(e)}