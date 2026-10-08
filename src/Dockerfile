FROM python:3.13-slim

ENV GROUP_NAME=app
ENV HOME=/app
ENV GROUP_ID=11000
ENV USER_ID=11001
ENV PORT=8080

RUN groupadd -g $GROUP_ID $GROUP_NAME && \
    useradd -u $USER_ID -g $GROUP_ID -m -d $HOME app

COPY . $HOME
WORKDIR $HOME

RUN apt-get update && apt-get install -y \
    gcc \
    pkg-config \
    libmariadb-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE $PORT

USER $USER_ID

ENTRYPOINT ["python"]
CMD ["main.py"]