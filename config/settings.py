from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SEGURIDAD BÁSICA (ENTORNO LOCAL)
# ==========================================
# En desarrollo DEBE ser True para ver los errores detallados.
DEBUG = True 

# En local, permitimos todos los hosts para evitar problemas.
ALLOWED_HOSTS = ['*']

# Clave secreta (Para producción deberás cambiarla y ocultarla)
SECRET_KEY = 'django-insecure-tu-clave-secreta-local-aqui-cambiar-en-produccion'

# ==========================================
# APLICACIONES INSTALADAS
# ==========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    #'django.contrib.gis', # <-- IMPORTANTE: Para PostGIS y mapas
    
    # Tus aplicaciones
    'usuarios',
    'tableros',
    'catalogos',
    #'datalake',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'config.wsgi.application'


# ==========================================
# BASE DE DATOS LOCAL (POSTGRESQL + POSTGIS)
# ==========================================
# Ajusta el USER y PASSWORD a los de tu instalación local de PostgreSQL.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql', # Motor geoespacial
        'NAME': 'tablerosn',
        'USER': 'postgres',
        'PASSWORD': 'admin', # <-- CAMBIA ESTO por tu contraseña de pgAdmin
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'options': '-c search_path=public,bronze,silver,gold'
        }
    }
}


# ==========================================
# VALIDACIÓN DE CONTRASEÑAS
# ==========================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==========================================
# INTERNACIONALIZACIÓN
# ==========================================
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# ==========================================
# ARCHIVOS ESTÁTICOS Y MEDIA
# ==========================================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==========================================
# CONFIGURACIÓN DE AUTENTICACIÓN Y USUARIOS
# ==========================================
AUTH_USER_MODEL = 'usuarios.Usuario'

# Estas rutas son el "fallback", pero CustomLoginView hace el trabajo real
LOGIN_REDIRECT_URL = '/'  
LOGOUT_REDIRECT_URL = 'login' # Aquí forzamos que el logout vaya al login
LOGIN_URL = 'login'       