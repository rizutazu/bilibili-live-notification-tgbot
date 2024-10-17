FROM python:3.12-alpine

WORKDIR /bilibili-live-notification-tgbot

ADD . /bilibili-live-notification-tgbot

RUN python3 -m pip install --no-deps --no-cache-dir -r requirements.txt

CMD python3 -m bili_live_noti_bot