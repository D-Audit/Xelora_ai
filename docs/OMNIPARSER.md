# OmniParser-only visual Excel mode

Xelora can operate Excel like a person: it focuses the visible Excel window,
uses Excel's native **Go To / Name Box** behavior to select a known range, and
then types, pastes, or uses a keyboard shortcut. OmniParser is used only when
Xelora must identify an unknown on-screen control such as a ribbon command or
dialog button.

This profile deliberately disables the Excel skill library, COM/API workbook
operations, and generated Python code. It still keeps the configured AI
provider as the task planner: OmniParser finds screen elements but cannot turn
a natural-language request into a sequence of actions by itself.

### What is used

| Request | Visual action | OmniParser call? |
| --- | --- | --- |
| “Go to `B12`” | Excel Go To / Name Box pathway (`Ctrl+G`) | No |
| “Write Total in `A1`” | Go To `A1`, then type into Excel | No |
| “Paste this table at `A1`” | Go To `A1`, then one atomic clipboard paste | No |
| “Fill this formula down” | Go To, type the formula, then Excel Fill Down | No |
| “Click the Sort button” or handle a dialog | Parse the narrow ribbon/popup area, then click the returned element centre | Yes |

Using the Name Box pathway for known ranges avoids an unnecessary full-screen
parse and is the fastest, most reliable way to write visible cell data.

### Install and start the parser

The parser runs as a **separate local process**. Keep it bound to `127.0.0.1`:
it receives screenshots and does not provide authentication itself.

1. Install [Miniconda or Anaconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html), then clone the official [Microsoft OmniParser repository](https://github.com/microsoft/OmniParser).
2. In PowerShell, create its separate Python environment and install its dependencies:

```powershell
git clone https://github.com/microsoft/OmniParser.git
cd OmniParser
conda create -n omni python=3.12
conda activate omni
pip install -r requirements.txt
```

3. Download the OmniParser model weights by following the current **Install**
section of the official repository, then start its FastAPI parser server on a
port that is not Xelora's port 8000:

```powershell
cd omnitool\omniparserserver
python -m omniparserserver --host 127.0.0.1 --port 8001
```

4. In a second terminal, confirm the parser is ready:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/probe/
```

It should return an `Omniparser API ready` message. Then set these values in
`backend/.env`:

```env
OMNIPARSER_ONLY_MODE=true
OMNIPARSER_URL=http://127.0.0.1:8001/parse/
OMNIPARSER_TIMEOUT_SECONDS=60
```

The OmniParser-only profile automatically forces `VISUAL_ONLY_MODE=true`,
disables `ENABLE_CODEGEN_LAYER`, and hides every Excel skill from the planner.
Restart Xelora after changing `.env`:

```powershell
cd <your-xelora-folder>\backend
.\venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

If `OMNIPARSER_URL` is blank or points to the Xelora backend itself, Xelora
will refuse to start in this profile rather than silently falling back to
skills or generated code.

### Florence clarification and speed

Xelora does **not** run or call Florence directly. The standard upstream
OmniParser server, however, currently starts its Florence2 caption model for
unlabelled icon descriptions. It is not a separate Xelora feature that can be
disabled from `backend/.env`. Do not run an additional Florence service.

If a deployment must avoid Florence entirely, it needs a custom
OmniParser-compatible parser service that returns the same `parsed_content_list`
response using detector/OCR-only output. Xelora will work with that endpoint,
but it will have weaker descriptions for unlabelled icons. For the standard
server, the speed optimisation already in Xelora is to avoid parser calls for
known ranges, keyboard shortcuts, typing, table pastes, formulas, and simple
formatting; it parses only ambiguous visual controls.

