FROM python:3.9

WORKDIR /code

COPY /src/requirements.txt .

RUN pip install -r requirements.txt

COPY src/ .

CMD ["python", "main.py"]