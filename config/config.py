import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'chams_medical_app_key')
    
    # Paths
    BASE_PATH = os.environ.get('BASE_PATH', './cache_slices')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads')
    PROCESSED_FOLDER = os.environ.get('PROCESSED_FOLDER', './processed')
    
    # File limits
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 1000 * 1024 * 1024))  # 1000MB
    ALLOWED_EXTENSIONS = {'nii', 'nii.gz', 'dcm', 'dicom', 'IMA'}
    ALLOWED_REPORT_TYPES = {'cbct', 'panoramic', 'cephalometric', 'intraoral'}
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Supabase Configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://intukonwqiiyokuagplg.supabase.co")
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImludHVrb253cWlpeW9rdWFncGxnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MjkzNTExMCwiZXhwIjoyMDY4NTExMTEwfQ.YdnqRdR4p34tci74mQhBR7Xtplh3cdUdnaDDRodutIY")
