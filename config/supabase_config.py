# config/supabase_config.py

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# بيانات الاتصال
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # أو SERVICE_ROLE_KEY

# إنشاء العميل
supabase: Client = None

def init_supabase():
    """
    إنشاء اتصال Supabase
    """
    global supabase
    
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Missing Supabase credentials in .env file")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize Supabase: {str(e)}")
        supabase = None
        return False

def get_supabase():
    """
    الحصول على عميل Supabase
    """
    global supabase
    
    if supabase is None:
        if not init_supabase():
            raise Exception("Supabase client not available")
    
    return supabase

def test_connection():
    """
    اختبار الاتصال
    """
    try:
        client = get_supabase()
        # اختبار بسيط
        result = client.rpc('now').execute()
        print("🔗 Supabase connection test passed")
        return True
    except Exception as e:
        print(f"⚠️ Connection test failed: {str(e)}")
        return False

# تهيئة تلقائية عند استيراد الملف
init_supabase()