FROM python:3.14-slim

# Python runtime defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set dir and user
ENV GROUP_NAME=app \
    USER_NAME=app \
    HOME=/app \
    GROUP_ID=11000 \
    USER_ID=11001 \
    PORT=8080

# Add user
RUN groupadd --gid $GROUP_ID $GROUP_NAME && \
    useradd --uid $USER_ID --gid $GROUP_ID --home-dir $HOME --create-home --shell /usr/sbin/nologin $USER_NAME

# Copy files and set working dir
WORKDIR $HOME

# Install python packages (install requirements first for better layer caching)
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . $HOME

# Open port
EXPOSE $PORT

# Set user
USER $USER_ID

# Run via gunicorn (production WSGI server)
CMD ["sh", "-c", "gunicorn --config gunicorn.conf.py --chdir src --bind 0.0.0.0:${PORT:-8080} main:app"]
