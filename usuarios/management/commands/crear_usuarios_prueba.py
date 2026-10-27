from django.core.management.base import BaseCommand
from usuarios.models import Usuario


USUARIOS = [
    ('admin_tlab',   'admin@tlab.local',   'Admin123!',   Usuario.Rol.ADMINISTRADOR),
    ('oper_tlab',    'oper@tlab.local',    'Oper123!',    Usuario.Rol.OPERADOR),
    ('dir_tlab',     'dir@tlab.local',     'Dir123!',     Usuario.Rol.DIRECTIVO),
    ('prensa_tlab',  'prensa@tlab.local',  'Prensa123!',  Usuario.Rol.PERIODISTA),
]


class Command(BaseCommand):
    help = 'Crea usuarios de prueba para cada rol del sistema.'

    def handle(self, *args, **options):
        for username, email, password, rol in USUARIOS:
            obj, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={'email': email, 'rol': rol, 'is_staff': rol == Usuario.Rol.ADMINISTRADOR},
            )
            if creado:
                obj.set_password(password)
                obj.save()
                self.stdout.write(self.style.SUCCESS(
                    f'✔ Creado: {username} / {password} ({obj.get_rol_display()})'
                ))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Ya existe: {username}'))