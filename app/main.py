import copy
import json
import logging
import re
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fake_erp")

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sales_order.json"
DEFAULT_ORDER = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

app = FastAPI(title="Fake ERP", description="Sales-order stand-in for MES upload tests")


def first_tag(body: str, tag: str) -> str:
    match = re.search(
        rf"<(?:[\w.-]+:)?{tag}(?:\s[^>]*)?>(.*?)</(?:[\w.-]+:)?{tag}>",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def looks_like_xml(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("<")


def build_sales_order(
    company_code: str | None,
    sales_order_id: str | None,
    request_uuid: str | None = None,
) -> dict:
    order = copy.deepcopy(DEFAULT_ORDER)
    if company_code:
        order["companyCode"] = company_code
    if sales_order_id:
        order["salesOrderID"] = sales_order_id
    if request_uuid:
        order["UUID"] = request_uuid
    return order


def post_webhook(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = UrlRequest(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            logger.info(
                "webhook %s uuid=%s -> %s",
                payload.get("salesOrderID"),
                payload.get("UUID"),
                response.status,
            )
    except URLError as error:
        logger.error(
            "webhook %s uuid=%s failed: %s",
            payload.get("salesOrderID"),
            payload.get("UUID"),
            error,
        )


@app.get("/health")
def health() -> dict:
    logger.info("GET /health")
    return {"status": "ok"}


@app.get("/erp/sales-orders/{sales_order_id}")
def get_sales_order(sales_order_id: str) -> JSONResponse:
    logger.info("GET /erp/sales-orders/%s", sales_order_id)
    order = build_sales_order(company_code=None, sales_order_id=sales_order_id)
    return JSONResponse(content=order)


@app.post("/erp/sales-orders")
async def post_sales_order(request: Request) -> Response:
    raw = await request.body()
    text = raw.decode("utf-8", errors="replace")
    logger.info("%s %s body=%s", request.method, request.url.path, text or "<empty>")

    if looks_like_xml(text):
        sales_order_id = first_tag(text, "SalesOrder")
        request_uuid = first_tag(text, "requestUUID")
        response_url = first_tag(text, "responseUrl")
        company_code = first_tag(text, "company") or None
        order_id = sales_order_id or None
        order = build_sales_order(company_code, order_id, request_uuid or None)

        logger.info(
            "soap salesOrder=%s uuid=%s responseUrl=%s",
            order_id,
            request_uuid,
            response_url,
        )

        if order_id and request_uuid and response_url:
            post_webhook(response_url, order)

        return Response(content="<response/>", media_type="text/xml")

    try:
        parsed = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    company_code = parsed.get("companyCode")
    sales_order_id = parsed.get("salesOrderID")
    company = company_code if isinstance(company_code, str) and company_code else None
    order_id = sales_order_id if isinstance(sales_order_id, str) and sales_order_id else None
    order = build_sales_order(company_code=company, sales_order_id=order_id)
    return JSONResponse(content=order)
