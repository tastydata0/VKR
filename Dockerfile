FROM python:3.10

WORKDIR /app

RUN apt-get update && apt-get install -y curl && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs

COPY ./package*.json /app/
COPY ./webpack.config.js /app/
COPY ./requirements.txt /app/requirements.txt

RUN npm install

RUN pip install --no-cache-dir --upgrade --progress-bar off -r /app/requirements.txt 

COPY ./src /app/src
COPY ./data /app/data

RUN npx webpack

EXPOSE 80
CMD ["uvicorn", "src.main:server.app", "--host", "127.0.0.1", "--port", "80"]
