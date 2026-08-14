"""Local OmniParser V2 client. It observes only; it never controls the mouse or keyboard."""

import base64
import io
from pathlib import Path
from uuid import uuid4

import requests

import config


def parse_image(image) -> dict:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    response = requests.post(
        config.OMNIPARSER_URL,
        json={"base64_image": encoded},
        timeout=config.OMNIPARSER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    width, height = image.size
    elements = []
    for index, raw in enumerate(payload.get("parsed_content_list", [])):
        bbox = raw.get("bbox") or raw.get("box") or raw.get("coordinates")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = (float(value) for value in bbox)
        if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.0:
            x1, x2, y1, y2 = x1 * width, x2 * width, y1 * height, y2 * height
        elements.append({
            "id": index,
            "description": str(raw.get("content", raw.get("text", "unlabeled element"))),
            "type": str(raw.get("type", "unknown")),
            "bbox": [round(x1), round(y1), round(x2), round(y2)],
            "center": [round((x1 + x2) / 2), round((y1 + y2) / 2)],
        })
    return {"elements": elements, "screen_size": [width, height], "latency": payload.get("latency")}
