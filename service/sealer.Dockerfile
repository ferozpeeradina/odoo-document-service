FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY service/requirements.txt /service/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /service/requirements.txt
COPY service/sealer.py service/verify.py /service/
ENTRYPOINT ["python", "/service/sealer.py"]
