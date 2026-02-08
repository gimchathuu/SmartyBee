import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-magic-bee'
    
    # Database Credentials
    # Users should set these environment variables or update defaults here
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or '' # XAMPP default: empty password
    DB_NAME = os.environ.get('DB_NAME') or 'smartybee_db'
