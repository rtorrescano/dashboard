# fix_db.py
from django.db import connection
from django.core.management import call_command

print("1. Ajustando search_path...")
with connection.cursor() as cur:
    cur.execute("ALTER DATABASE tablerosn SET search_path TO public, bronze;")
    cur.execute("SET search_path TO public, bronze;")

print("2. Eliminando tablas parciales de Django en public...")
with connection.cursor() as cur:
    for t in [
        "django_admin_log", "auth_permission", "auth_group_permissions",
        "auth_group", "usuarios_usuario_groups",
        "usuarios_usuario_user_permissions", "usuarios_usuario",
        "django_session", "django_content_type", "django_migrations",
    ]:
        cur.execute(f"DROP TABLE IF EXISTS public.{t} CASCADE;")
    print("   OK")

print("3. Creando public.django_migrations con SOLO las apps que NO son de Django...")
with connection.cursor() as cur:
    cur.execute("""
        CREATE TABLE public.django_migrations (
            id serial PRIMARY KEY,
            app varchar(255) NOT NULL,
            name varchar(255) NOT NULL,
            applied timestamp with time zone NOT NULL
        )
    """)
    cur.execute("""
        INSERT INTO public.django_migrations (app, name, applied)
        SELECT app, name, applied
        FROM bronze.django_migrations
        WHERE app NOT IN ('admin', 'auth', 'contenttypes', 'sessions', 'usuarios')
    """)
    cur.execute("SELECT count(*) FROM public.django_migrations;")
    print("   Migraciones previas conservadas:", cur.fetchone()[0])

print("4. Ejecutando migrate (creara admin/auth/sessions/usuarios en public)...")
call_command("migrate", verbosity=1, interactive=False)

print("5. Copiando usuarios de bronze a public...")
with connection.cursor() as cur:
    cur.execute("""
        INSERT INTO public.usuarios_usuario
            (id, password, last_login, is_superuser, username, first_name,
             last_name, email, is_staff, is_active, date_joined, rol)
        SELECT id, password, last_login, is_superuser, username, first_name,
               last_name, email, is_staff, is_active, date_joined, rol
        FROM bronze.usuarios_usuario
        ON CONFLICT (username) DO NOTHING;
    """)
    cur.execute("""
        SELECT setval(
            pg_get_serial_sequence('public.usuarios_usuario', 'id'),
            COALESCE((SELECT MAX(id) FROM public.usuarios_usuario), 1)
        );
    """)

print("6. Verificando...")
with connection.cursor() as cur:
    cur.execute("SELECT current_schema();")
    print("   Esquema activo:", cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM public.usuarios_usuario;")
    print("   Usuarios en public:", cur.fetchone()[0])
    cur.execute("SELECT username, rol FROM public.usuarios_usuario ORDER BY username;")
    for r in cur.fetchall():
        print("   ", r)