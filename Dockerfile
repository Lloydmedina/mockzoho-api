FROM node:22-slim AS ui-build
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=ui-build /app/static/ui /app/app/static/ui

EXPOSE 8090

CMD ["sh", "-c", "pytest -v tests/ && uvicorn app.main:app --host 0.0.0.0 --port 8090"]
