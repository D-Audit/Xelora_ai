---
name: insert_picture
category: dashboard
description: "Places an image file (logo, icon, screenshot) onto a sheet at a given cell anchor. The image file must already exist on disk."
source: new (gap closure)
---

# insert_picture

Places an image file (logo, icon, screenshot) onto a sheet at a given cell anchor. The image file must already exist on disk.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "image_path": {
      "type": "string"
    },
    "anchor_cell": {
      "type": "string"
    },
    "width": {
      "type": "number"
    },
    "height": {
      "type": "number"
    }
  },
  "required": [
    "sheet_name",
    "image_path",
    "anchor_cell"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
