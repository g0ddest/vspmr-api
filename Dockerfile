# Use the official Python image as a base
FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

ENV FLASK_RUN_HOST=0.0.0.0

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]