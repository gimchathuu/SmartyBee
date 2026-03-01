import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-magic-bee'
    
    # Database Credentials
    # Users should set these environment variables or update defaults here
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or '' # XAMPP default: empty password
    DB_NAME = os.environ.get('DB_NAME') or 'smartybee_db'

    # ML Model Settings
    USE_ML_MODEL = os.environ.get('USE_ML_MODEL', 'true').lower() == 'true'
    ML_WEIGHT = float(os.environ.get('ML_WEIGHT', '0.8'))  # 0.0=template only, 1.0=ML only
    COLLECT_TRAINING_DATA = True  # Always collect data for future training
