FROM alpine:latest

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    python3 -m pip install --no-cache --upgrade pip setuptools

RUN python3 -m pip install \
    --index-url https://test.pypi.org/simple/ \
    --no-deps \
    resht-jkfillmore

ENTRYPOINT ['resht']
