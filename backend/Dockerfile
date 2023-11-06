FROM python:3.8

WORKDIR /app

COPY . .

RUN pip install psycopg2
RUN pip install aiogram
RUN pip install croniter
RUN pip install pytz

CMD [ "python", "./main.py" ]