FROM python:3.10

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./src /app/src
COPY ./data /app/data
COPY ./install_py_packages.sh /app/install_py_packages.sh

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"]
