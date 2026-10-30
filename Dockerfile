FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /application

COPY requirements.txt .
COPY docker_wheels ./docker_wheels
# Si docker_wheels/ contient les paquets (téléchargés à l'avance par scripts/download_docker_wheels.ps1), installation
# SANS Internet : le réseau de Docker sous WSL est trop instable vers PyPI (téléchargements coupés observés).
# Sinon, installation depuis PyPI avec réessais. Le dossier est supprimé ensuite pour alléger l'image.
RUN if ls docker_wheels/*.whl > /dev/null 2>&1; then \
        pip install --no-cache-dir --no-index --find-links docker_wheels -r requirements.txt; \
    else \
        pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt; \
    fi \
    && rm -rf docker_wheels

COPY alembic.ini .
COPY backend ./backend
COPY web_interface ./web_interface
COPY db ./db
COPY scripts ./scripts

# Fichiers lisibles par tous : COPY conserve les droits du dossier d'origine. Depuis un dossier partagé VirtualBox
# (droits 0770, groupe vboxsf), alembic.ini serait illisible pour le compte non-root ci-dessous, et Alembic
# échouerait avec « No 'script_location' key found in configuration ».
RUN chmod -R a+rX /application

# Compte non-root : le backend n'a pas besoin de privilèges.
RUN useradd --create-home backend_runner
USER backend_runner

# 8000 : interface et API ; 5140 : réception syslog des logs FortiAnalyzer (SYSLOG_LISTEN_PORT).
EXPOSE 8000 5140/udp 5140/tcp
CMD ["uvicorn", "backend.main:application", "--host", "0.0.0.0", "--port", "8000"]
