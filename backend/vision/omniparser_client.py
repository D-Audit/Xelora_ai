"""Local OmniParser V2 client. It observes only; it never controls the mouse or keyboard."""

import base64
import io
import math
import time

import requests

import config


def parse_image(image, retries: int = 3) -> dict:
    """Parse a PIL Image into structured UI elements.

    Routing:
    - OMNIPARSER_LOCAL_MODE=true  →  run YOLOv9 + Florence-2 in-process
    - OMNIPARSER_URL set          →  call external HTTP service
    - neither configured          →  raise RuntimeError

    Retries transient failures (model load, OCR hiccup, network blip) with
    exponential backoff before giving up, so a single bad frame doesn't abort a task.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if config.OMNIPARSER_LOCAL_MODE:
                return _parse_local(image)
            return _parse_http(image)
        except Exception as exc:  # noqa: BLE001 - we retry any transient parser failure
            last_exc = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(
        f"OmniParser failed after {retries} attempts: {last_exc}"
    ) from last_exc


def _parse_local(image) -> dict:
    """Run OmniParser locally — no external service needed."""
    from vision.local_omniparser import parse_image_local
    return parse_image_local(image)


def _parse_http(image) -> dict:
    """Call the external OmniParser HTTP service."""
    if not config.OMNIPARSER_URL:
        raise RuntimeError(
            "OmniParser is not configured. Set OMNIPARSER_URL to a separately running "
            "parser service, or set OMNIPARSER_LOCAL_MODE=true to run locally."
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    try:
        response = requests.post(
            config.OMNIPARSER_URL,
            json={"base64_image": encoded},
            timeout=config.OMNIPARSER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.ConnectionError as exc:
        raise RuntimeError(
            "The optional OmniParser service is not running at "
            f"{config.OMNIPARSER_URL}. Excel is still available, but visual element "
            "recognition cannot be used. Start the parser service or set "
            "OMNIPARSER_LOCAL_MODE=true for local inference."
        ) from exc
    except requests.Timeout as exc:
        raise RuntimeError(
            "The optional OmniParser service did not respond before the configured timeout. "
            "Excel is still available, but visual element recognition cannot be used."
        ) from exc
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise RuntimeError(
                "The configured OmniParser endpoint returned 404. Set OMNIPARSER_URL to the "
                "separately running parser service's /parse/ endpoint, not the FastAPI backend."
            ) from exc
        raise RuntimeError(f"OmniParser request failed: {exc}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"OmniParser request failed: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("OmniParser returned a non-JSON response; refusing to use unverified screen coordinates.") from exc

    raw_elements = payload.get("parsed_content_list")
    if not isinstance(raw_elements, list):
        raise RuntimeError(
            "OmniParser returned an unexpected response shape; refusing to use unverified screen coordinates."
        )

    width, height = image.size
    elements = []
    for index, raw in enumerate(raw_elements):
        if not isinstance(raw, dict):
            continue
        bbox = raw.get("bbox") or raw.get("box") or raw.get("coordinates")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            x1, y1, x2, y2 = (float(value) for value in bbox)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            continue
        # Detect normalized vs pixel coordinates
        if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.0:
            x1, x2, y1, y2 = x1 * width, x2 * width, y1 * height, y2 * height
        x1, x2 = sorted((max(0.0, min(x1, width)), max(0.0, min(x2, width))))
        y1, y2 = sorted((max(0.0, min(y1, height)), max(0.0, min(y2, height))))
        if x2 <= x1 or y2 <= y1:
            continue
        elements.append({
            "id": index,
            "description": str(raw.get("content", raw.get("text", "unlabeled element"))),
            "type": str(raw.get("type", "unknown")),
            "bbox": [round(x1), round(y1), round(x2), round(y2)],
            "center": [round((x1 + x2) / 2), round((y1 + y2) / 2)],
        })
    return {"elements": elements, "screen_size": [width, height], "latency": payload.get("latency")}
