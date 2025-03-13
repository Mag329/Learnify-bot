FROM python:3.11-slim-buster

# Install locales and generate the ru_RU.UTF-8 locale
RUN apt-get update && apt-get install -y \
    locales \
    && sed -i '/^#.*ru_RU.UTF-8/s/^#//g' /etc/locale.gen \
    && locale-gen ru_RU.UTF-8 \
    && update-locale LANG=ru_RU.UTF-8 \
    && apt-get clean

WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . src

COPY alembic.ini .
COPY alembic/ alembic/

RUN alembic upgrade head

CMD ["python3", "src/run.py"]