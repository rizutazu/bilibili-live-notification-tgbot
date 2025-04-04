FROM python:3.12-alpine

WORKDIR /usr/src/bilibili-live-notification-tgbot

COPY . /usr/src/bilibili-live-notification-tgbot

RUN python3 -m pip install --no-cache-dir -r requirements.txt

CMD python3 -u -m bili_live_noti_bot