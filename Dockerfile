FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY conduit/ conduit/
COPY examples/ examples/
EXPOSE 8443
CMD ["conduit", "serve", "--config", "examples/conduit.yaml", "--port", "8443"]
