import os
from dotenv import load_dotenv # Keep this for python-dotenv
from pathlib import Path
import dj_database_url
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') # Changed from SECRET_KEY to DJANGO_SECRET_KEY for clarity



DEBUG = os.getenv('DEBUG', '0').lower() in ['1', 'true', 't']

ALLOWED_HOSTS = ['sipcassmodelbackend.onrender.com', 'localhost', '127.0.0.1', '.onrender.com']

# Add this right after ALLOWED_HOSTS
if 'RENDER' in os.environ:
    ALLOWED_HOSTS.append(os.environ.get('RENDER_EXTERNAL_HOSTNAME', ''))
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}")


if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # For Render's proxy
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --- Installed Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'api', # Your custom app
    'corsheaders',
    # 'storages', # Add this if you go with S3/GCS for media files
]

# --- Middleware ---
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # For static files (correctly placed)
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --- URL Configuration ---
ROOT_URLCONF = 'sipcass.urls'

# --- Templates ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# --- WSGI Application ---
WSGI_APPLICATION = 'wsgi.application'

# Database (PostgreSQL - Render provides this)
DATABASES = {
    'default': dj_database_url.config(default=os.getenv('DATABASE_URL'))
}


# --- Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True # Keep this True, especially with PostgreSQL

CSRF_TRUSTED_ORIGINS = ["https://sipcassmodelbackend.onrender.com","https://sipcassmodel-backend.onrender.com"]

# --- Media Files (User Uploads) ---
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# --- Static Files (WhiteNoise) ---
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- Default Primary Key Field ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CORS Headers Settings ---
CORS_ALLOWED_ORIGINS = [
    "https://sipcassmodel-frontend.vercel.app",
    "http://localhost:3000",  # For local testing
]

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]