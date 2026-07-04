"""
vision/decision_loop.py
This is the piece that was flagged as missing: the primitives in
ui_control.py (screenshot/click/type) existed, but nothing decided
WHERE to click. This module closes that loop: take a screenshot, ask a
vision-capable model to locate the described element by pixel
coordinates, then click there.

Registered as a single skill (click_on_screen_element) rather than
exposing "take a screenshot" and "click at x,y" as two separate steps
the planning AI has to sequence itself - this keeps it atomic and
harder to misuse (the coordinates never leave this function without
immediately being acted on).

Only used as the third layer (after skill library and code generation
both come up empty) - see agent/prompts.py's ordering. Off by default
(ENABLE_VISUAL_FALLBACK=false) since it needs a real desktop display
and burns an extra AI call (with an image) per use.
"""

import base64
import json
import tempfile

import config
from skills.base import skill
from vision import ui_control


def _ask_model_for_coordinates(image_path: str, element_description: str) -> dict:
    """Sends the screenshot to Claude with a vision prompt asking for the
    pixel location of the described element. Returns {"x": int, "y": int,
    "found": bool, "reasoning": str}. Requires ANTHROPIC_API_KEY - this
    step specifically needs a vision-capable model regardless of which
    AI_PROVIDER is driving the main task loop, since not every provider
    path here has vision wired up identically."""
    from anthropic import Anthropic

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": (
                    f"Find the screen element described as: '{element_description}'. "
                    "Respond with ONLY a JSON object, no other text: "
                    '{"found": true/false, "x": <pixel x>, "y": <pixel y>, "reasoning": "<brief reason>"}. '
                    "Coordinates should be the center point to click, in this image's own pixel dimensions."
                )},
            ],
        }],
    )

    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"found": False, "reasoning": f"Model did not return valid JSON: {text[:200]}"}


@skill(
    name="click_on_screen_element",
    description=(
        "Visual fallback (use only after skills and code generation can't do this): takes a "
        "screenshot, asks a vision model to find an on-screen element by description (e.g. "
        "'the OK button in the dialog box', 'the Insert tab in the ribbon'), and clicks it. "
        "Requires a real desktop display - does not work on a headless server."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "element_description": {"type": "string"},
            "double_click": {"type": "boolean"},
        },
        "required": ["element_description"],
    },
    category="vision",
)
def click_on_screen_element(element_description: str, double_click: bool = False):
    if not config.ENABLE_VISUAL_FALLBACK:
        return {"status": "disabled", "verified": False,
                "verification_note": "Visual fallback is disabled (ENABLE_VISUAL_FALLBACK=false in .env)."}

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        screenshot_path = f.name

    try:
        ui_control.screenshot_active_window(screenshot_path)
    except RuntimeError as e:
        return {"status": "no_display", "verified": False, "error": str(e)}

    location = _ask_model_for_coordinates(screenshot_path, element_description)

    if not location.get("found"):
        return {"status": "not_found", "verified": False, "element_description": element_description,
                "reasoning": location.get("reasoning", "Model could not locate the element.")}

    click_result = ui_control.click_at(location["x"], location["y"], double=double_click)

    return {
        "status": "clicked", "element_description": element_description,
        "coordinates": {"x": location["x"], "y": location["y"]},
        "reasoning": location.get("reasoning"), "verified": True,
        "verification_note": "Clicked at the model's identified coordinates - this does not "
            "confirm the click had the intended effect, only that a click occurred there. "
            "Follow up with inspect_workbook or read_range to confirm the actual result.",
    }
