FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

ENV FLASK_RUN_HOST=0.0.0.0

CMD ["python3", "vspmr_initiation_parser.py"]