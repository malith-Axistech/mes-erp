# Fake ERP

A small HTTP stand-in for the ERP. MES sales-order import still talks to LN with SOAP, then waits for a webhook. This app answers that SOAP and posts the webhook with fixture sales-order data so import can be tested locally.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8765
```

Point MES at `http://host.docker.internal:8765/erp/sales-orders` (`LN_ERP_URL`). Keep `WEBHOOK_APP_URL` as the MES webhook, e.g. `http://127.0.0.1:8001/webhook`.

## Docker

```bash
docker compose up -d
```

`WEBHOOK_HOST_ALIAS` rewrites a `127.0.0.1` or `localhost` webhook address so the container can reach MES on the Mac.

Do not use `mes/scripts/sales-order-erp-simulator.py` for this flow.

## Endpoints

- `GET /health` — liveness check.
- `POST /erp/sales-orders` — MES SOAP (`Content-Type: text/xml`) with `SalesOrder`, `requestUUID`, and `responseUrl`. The app copies the id onto the fixture document, sets `UUID`, POSTs JSON to `responseUrl`, then returns `<response/>`. JSON POST still returns the document in the HTTP body (optional `companyCode`, `salesOrderID`).
- `GET /erp/sales-orders/{salesOrderID}` — same document, with that sales order id.

`VEN028045` with company `100` matches the shipped fixture, including padded item and name fields and both lines.
