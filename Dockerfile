FROM python:3.13-slim

# Install locales and generate the ru_RU.UTF-8 locale
RUN apt-get update && apt-get install -y \
    locales \
    git \
 && sed -i '/^#.*ru_RU.UTF-8/s/^#//g' /etc/locale.gen \
 && locale-gen ru_RU.UTF-8 \
 && update-locale LANG=ru_RU.UTF-8 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

CMD ["python3", "run.py"]