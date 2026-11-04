# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS frontend-dev
WORKDIR /workspace/src/frontend
COPY src/frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY src/frontend/ ./
CMD ["npm", "run", "dev"]

FROM frontend-dev AS frontend-build
RUN npm run build

FROM python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f AS backend-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace/src
WORKDIR /workspace
COPY requirements.txt requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.lock

FROM backend-base AS tools
COPY requirements-dev.txt requirements-dev.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.lock
COPY pyproject.toml ./

FROM tools AS backend-dev
COPY src/hackbrew/ src/hackbrew/
CMD ["uvicorn", "hackbrew.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM backend-base AS thermal-simulator
COPY src/hackbrew/ src/hackbrew/
CMD ["uvicorn", "hackbrew.thermal_simulator:app", "--host", "0.0.0.0", "--port", "8000"]

FROM tools AS browser-deps
RUN python -m playwright install --with-deps --only-shell chromium

FROM browser-deps AS tests
COPY --from=gateway /main.py /ble_worker.py /config.py /http_worker.py /registry.py /replay.py /telemetryData.py /requirements.lock /opt/rapt-gateway/
COPY --from=gateway /fixtures /opt/rapt-gateway/fixtures/
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /opt/rapt-gateway/requirements.lock
COPY tests/ tests/
CMD ["pytest"]

FROM backend-base AS runtime
RUN useradd --uid 10001 --create-home hackbrew
COPY src/hackbrew/ src/hackbrew/
COPY --from=frontend-build /workspace/src/frontend/dist /workspace/frontend-dist
ENV HACKBREW_FRONTEND_DIST=/workspace/frontend-dist
USER hackbrew
EXPOSE 8000
CMD ["uvicorn", "hackbrew.app:app", "--host", "0.0.0.0", "--port", "8000"]
