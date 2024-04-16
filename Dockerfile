FROM python:3.10

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade --progress-bar off -r /app/requirements.txt 

COPY ./src /app/src
COPY ./data /app/data

EXPOSE 80
CMD ["uvicorn", "src.main:server.app", "--host", "127.0.0.1", "--port", "80"]
