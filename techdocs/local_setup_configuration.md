# 🛠 Configuração e Execução do Taiga

Este guia contém o passo a passo para configurar o ambiente e rodar o **Taiga** no seu sistema.

## 📌 Passo 1: Verificar versão do Python
```bash
python3 --version
```
## 📌 Passo 2: Instalar pacotes essenciais do sistema

```bash
sudo apt-get update && sudo apt-get install -y build-essential binutils-doc autoconf flex bison \
    libjpeg-dev libfreetype6-dev zlib1g-dev libzmq3-dev libgdbm-dev libncurses5-dev \
    automake libtool curl git tmux gettext
```
## 📌 Passo 3: Navegar até o diretório do projeto

```bash
cd ~/Documents/Projetos/taiga/taiga-back/
ls
```
## 📌 Passo 4: Instalar suporte a ambientes virtuais no Python

```bash
sudo apt-get install python3-venv
```
## 📌 Passo 5: Criar o ambiente virtual

```bash
python3 -m venv .venv
```
```bash
sudo apt update && sudo apt install -y python3.10 python3.10-venv python3.10-dev
python3.10 -m venv .venv
```
```bash
ls
```
## 📌 Passo 6: Ativar o ambiente virtual

```bash
source .venv/bin/activate
```
## 📌 Passo 7: Atualizar pacotes do Python

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install --upgrade pip-tools
pip install pycparser
pip install --upgrade build
pip install --upgrade "build<0.11.0"
```
## 📌 Passo 8: Instalar dependências do projeto

```bash
pip install -r requirements.txt
pip install -r requirements-devel.txt
pip install -r requirements-tests.txt
pip list  # Confirme que todas as dependências foram instaladas corretamente
```
## 📌 Passo 9: Instalar taiga-contrib-protected

```bash
pip install git+https://github.com/celtab/apps-tadt/taigaio/taiga-contrib-protected.git@stable#egg=taiga-contrib-protected
```
## 📌 Passo 10: Configurar variáveis de ambiente

```bash
cp .env.example .env
```
## 📌 Passo 11: Subir o banco de dados com Docker

```bash
cd dockerdb/
docker compose up -d
cd ..
```
## 📌 Passo 11.1: Entrar no container
```
docker exec -it taiga-back bash
```
```
apt-get update
```
```
apt-get install -y gettext

```

## 📌 Passo 12: Rodar as migrações do Django

```bash
DJANGO_SETTINGS_MODULE=settings.config python manage.py migrate --noinput
```
## 📌 Passo 13: Criar usuário administrador

```bash
CELERY_ENABLED=False DJANGO_SETTINGS_MODULE=settings.config python manage.py createsuperuser
```
## 📌 Passo 14: Carregar os dados iniciais

```bash
DJANGO_SETTINGS_MODULE=settings.config python manage.py loaddata initial_project_templates
```
## 📌 Passo 15: Compilar mensagens de tradução

```bash
DJANGO_SETTINGS_MODULE=settings.config python manage.py compilemessages
```
## 📌 Passo 16: Coletar arquivos estáticos

```bash
DJANGO_SETTINGS_MODULE=settings.config python manage.py collectstatic --noinput
```
## 📌 Passo 17: Popular banco de dados com dados de exemplo

```bash
CELERY_ENABLED=False DJANGO_SETTINGS_MODULE=settings.config python manage.py sample_data

```
## 📌 Passo 18: Rodar o servidor Django

```bash
DJANGO_SETTINGS_MODULE=settings.config python manage.py runserver
```
Agora o Taiga deve estar rodando corretamente! 🚀
Se tiver qualquer problema, verifique as mensagens de erro e tente os comandos de diagnóstico.


```bash
docker ps  # Verificar se os containers do banco estão rodando
pip list   # Conferir se todas as dependências foram instaladas

```