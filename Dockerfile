FROM python:latest

RUN pip install kucoin-python
COPY ./ /usr/src/app/
WORKDIR /usr/src/app
CMD ["./trade.py"]