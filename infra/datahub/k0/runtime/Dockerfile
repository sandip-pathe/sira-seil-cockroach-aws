FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df

ARG COMPONENT_ID=adapter
LABEL org.opencontainers.image.title="SIRA K0 proof runtime" \
      io.sira.proof.component="${COMPONENT_ID}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMPONENT_ID="${COMPONENT_ID}"

WORKDIR /app
COPY adapter_server.py router_server.py router_probe.py campaign_probe.py /app/
RUN mkdir -p /run/proof /state && chown -R 65532:65532 /app /run/proof /state

USER 65532:65532
CMD ["python", "/app/adapter_server.py"]
