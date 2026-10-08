from django.core.management.base import BaseCommand
from taiga.projects.models import Project
from PIL import Image, UnidentifiedImageError
from io import BytesIO


class Command(BaseCommand):
    help = "Verifica se os arquivos de logo dos projetos estão válidos e legíveis"

    def handle(self, *args, **options):
        self.stdout.write("Verificando logos dos projetos...\n")

        projetos_invalidos = 0
        for project in Project.objects.exclude(logo=""):
            try:
                image_data = project.logo.read()
                image = Image.open(BytesIO(image_data))
                width, height = image.size
                project.logo.seek(0)

                if width == 0 or height == 0:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[Dimensões inválidas] Projeto '{project.name}' (ID={project.id}) — {width}x{height}"
                        )
                    )
                    projetos_invalidos += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"[OK] Projeto '{project.name}' — {width}x{height}")
                    )
            except FileNotFoundError:
                self.stdout.write(
                    self.style.ERROR(
                        f"[Arquivo ausente] Projeto '{project.name}' (ID={project.id}) — Caminho: {project.logo.name}"
                    )
                )
                projetos_invalidos += 1
            except UnidentifiedImageError:
                self.stdout.write(
                    self.style.ERROR(
                        f"[Imagem inválida] Projeto '{project.name}' (ID={project.id}) — Não reconhecida como imagem."
                    )
                )
                projetos_invalidos += 1
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"[Erro inesperado] Projeto '{project.name}' (ID={project.id}) — {str(e)}"
                    )
                )
                projetos_invalidos += 1

        if projetos_invalidos == 0:
            self.stdout.write(self.style.SUCCESS("\nTodas as logos estão válidas!"))
        else:
            self.stdout.write(
                self.style.WARNING(f"\nForam encontradas {projetos_invalidos} logos com problema.")
            )
