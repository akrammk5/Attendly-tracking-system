FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV DJANGO_DEBUG=0
RUN DJANGO_SECRET_KEY=build-only-not-a-secret ATTENDLY_TEST_SQLITE=1 python manage.py collectstatic --noinput
USER appuser
EXPOSE 8000
CMD ["gunicorn","attendly.wsgi:application","--bind","0.0.0.0:8000","--workers","3","--access-logfile","-","--error-logfile","-"]
