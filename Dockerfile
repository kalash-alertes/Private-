FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /application

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY backend ./backend
COPY db ./db

# Compte non-root : le backend n'a pas besoin de privilèges.
RUN useradd --create-home backend_runner
USER backend_runner

EXPOSE 8000
CMD ["uvicorn", "backend.main:application", "--host", "0.0.0.0", "--port", "8000"]
