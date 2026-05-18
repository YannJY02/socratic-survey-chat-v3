# 💬 surveychat

[![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://github.com/ellerbrock/open-source-badges/)
![GitHub License](https://img.shields.io/github/license/surveychat/surveychat)

This repository is a thesis-specific Streamlit adaptation of `surveychat` for an online experiment about research-design learning. The current study uses Qualtrics for consent, background items, randomization, later questionnaire blocks, posttest, debriefing, and copy-back capture. Streamlit owns only the learning sequence, the AI-supported problem-solving interface, the `RSM count` item, and the minimal completion/process JSON payload.

> Simple setup instructions [here](https://surveychat.github.io/).

> **Demo:** Try an experimental setup [here](https://surveychat.invisible.info) — use code ALPHA for a neutral chatbot, and BETA for an empathetic chatbot. This demo uses the open-source model `gpt-oss-120b`.

Current study flow:

- Qualtrics randomizes participants and stores the interpretable condition internally.
- Qualtrics passes only an opaque `route_code` to Streamlit.
- Streamlit maps that route code to the phase order and keeps the same Socratic tutor behavior across routes.
- The participant-visible copy-back payload may include the opaque `route_code`, but it must not expose `condition_internal`, `I_PS`, `PS_I`, `I->PS`, `PS->I`, model names, API endpoints, keys, headers, or other sensitive implementation details.
- The formal copy-back payload does not include the full AI-chat transcript or the text entered in the `Study ideas to submit` box.

AI backend provider configuration is handled separately from this README and remains a deployment/approval decision. Do not infer the approved provider route from generic examples below.



Entering a passcode (experiment mode only):

![Passcode entry](paper/surveychat-interface-1.png)

Chatting with the bot:

![Chat interface](paper/surveychat-interface-2.png)

Copying the study data when done:

![Study data export](paper/surveychat-interface-3.png)

---

## Before you start

You will need:

- **Python 3.10 or newer.** Check by running `python3 --version` in your terminal. If you don't have Python, download it from [python.org](https://www.python.org/downloads/).
- **An API key and endpoint.** surveychat uses a large language model (LLM) to power the chatbot. You will need an API key from any compatible provider (OpenAI, Azure, OpenRouter, or a local proxy). The key is stored in the `OPENAI_API_KEY` environment variable by convention. You will also set `API_BASE_URL` in `app.py` to point to your provider's chat-completions endpoint (see [Step 3 - Optional settings](#step-3---optional-settings)).
- **A terminal.** On macOS/Linux open **Terminal**. On Windows open **Command Prompt** or **PowerShell**.

---

## Quick start

**Step 1 - Fork the repo**

Click **Fork** at the top right of this GitHub page. This creates your own copy of surveychat under your GitHub account, which you can edit and deploy freely.

**Step 2 - Clone your fork to your computer**

Replace `YOUR_USERNAME` with your GitHub username:

```bash
git clone https://github.com/YOUR_USERNAME/surveychat.git
cd surveychat
pip install -r requirements.txt
cp .env.example .env
```

> **Don't have git?** Download it from [git-scm.com](https://git-scm.com/downloads) (free). On macOS it may already be installed - check with `git --version` in your terminal.

Now open the file called `.env` in any text editor and replace `your-key-here` with your actual API key:

```
OPENAI_API_KEY=sk-...
```

Save the file, then start the app by running this command in the terminal:

```bash
streamlit run app.py
```

Your browser will open automatically at http://localhost:8501. You should see the chatbot interface.

> **Note:** This URL only works on your own computer. To let participants access the chatbot, you will need to deploy it — see [Deployment](#deployment).

---

## Configuration

All settings live at the top of the file `app.py` inside a clearly marked section. You do not need to touch any other part of the file.

Open `app.py` in a text editor and find the block that begins:

```
# ╔══════════ RESEARCHER CONFIGURATION ═══════════╗
```

Everything you need to change is between that line and the matching closing line.

---

### Step 1 - Choose your mode

Set `N_CONDITIONS` to the number of different chatbot versions you need:

```python
N_CONDITIONS = 1   # survey mode  - one chatbot for everyone
N_CONDITIONS = 2   # experiment mode - A/B test (two versions)
N_CONDITIONS = 3   # experiment mode - three versions, and so on
```

---

### Step 2 - Write your chatbot instructions

The `CONDITIONS` list defines each chatbot version. Each version is a block of settings inside curly braces `{ }`.

**Survey mode example** (`N_CONDITIONS = 1`):

```python
CONDITIONS = [
    {
        "name":          "Interview bot",
        "system_prompt": "You are a friendly research interviewer. Ask one open-ended question at a time about the participant's social media habits. After 5–6 exchanges, thank them and let them know they can click End this chat.",
        "model":         "gpt-oss-120b",
    },
]
```

**Experiment mode example** (`N_CONDITIONS = 2`):

```python
CONDITIONS = [
    {
        "name":          "Condition A - Neutral",
        "passcode":      "ALPHA",
        "system_prompt": "You are a neutral research assistant. Answer questions clearly and factually without expressing opinions.",
        "model":         "gpt-oss-120b",
    },
    {
        "name":          "Condition B - Empathetic",
        "passcode":      "BETA",
        "system_prompt": "You are a warm, empathetic research assistant. Acknowledge the participant's feelings before responding.",
        "model":         "gpt-oss-120b",
    },
]
```

**What each field means:**

| Field | Required? | What it does |
|---|---|---|
| `"name"` | Always | A label for your own reference. Participants never see this. |
| `"passcode"` | Experiment mode only | The code a participant enters to reach this condition. Case-insensitive (`"alpha"` and `"ALPHA"` are the same). Leave this out when `N_CONDITIONS = 1`. |
| `"system_prompt"` | Always | The hidden instruction that tells the chatbot how to behave. Participants never see this text. |
| `"model"` | Always | Which AI model to use. Ask your lab coordinator which model name to use. |

---

### Step 3 - Optional settings

```python
API_BASE_URL = "https://api.openai.com/v1"
# The base URL for your LLM provider's chat-completions endpoint.
# Common values:
#   OpenAI:       "https://api.openai.com/v1"
#   OpenRouter:   "https://openrouter.ai/api/v1"
#   HuggingFace:  "https://api-inference.huggingface.co/v1"
#                 (set OPENAI_API_KEY to your HF token; set "model" to
#                  the HF model ID, e.g. "meta-llama/Llama-3.3-70B-Instruct")
#   Local model:  "http://localhost:1234/v1"
# Any chat-completions-compatible endpoint will work.

STUDY_TITLE = "surveychat"
# The name shown in the browser tab and at the top of the page.
# Change this to your study name, e.g. "Climate Attitudes Study".

WELCOME_MESSAGE = (
    "You are about to have a short conversation with an AI assistant. "
    "When you are finished, click the <strong>End chat</strong> button and complete the final check, "
    "then paste the study data back into the survey."
)
# A message shown to participants before they start chatting.
# Leave as "" for no message.

PASSCODE_ENTRY_PROMPT = "Please enter the passcode you received in the survey to begin chatting."
# The instruction shown above the passcode box (experiment mode only).
```

---

## Study-data copy-back format

```json
{
  "schema_version": "chatbot_stage_v1",
  "route_code": "Q4M9K2",
  "completion_status": "complete",
  "total_duration_seconds": 612.448,
  "phase_records": [
    {
      "phase": "instruction",
      "duration_seconds": 181.226
    }
  ],
  "rsm_count": {
    "value": "3 ideas"
  },
  "process_metadata": {
    "participant_message_count": 4,
    "assistant_message_count": 4,
    "study_ideas_submitted": true,
    "study_ideas_char_count": 842
  },
  "errors": []
}
```

The copy-back JSON contains completion and process metadata only:
- `route_code` - the opaque route code passed from Qualtrics; recover condition from Qualtrics embedded data, not from this payload
- `phase_records` - phase labels and relative durations only, without absolute timestamps
- `rsm_count` - the participant's response to the final RSM count item
- `process_metadata` - low-risk counts such as participant/assistant turn counts and submitted-ideas character count
- `errors` - coarse recovered-error metadata, if any


**Note:** The formal dataset should not include the full AI-chat transcript or the text typed in the `Study ideas to submit` box.

Parse in Python:
```python
import json, pandas as pd
data = json.loads(study_data_string)        # study_data_string is the text they pasted
phase_df = pd.DataFrame(data["phase_records"])
metadata = data["process_metadata"]
```

Parse in R:
```r
library(jsonlite)
data <- fromJSON(study_data_string)
phase_df <- as.data.frame(data$phase_records)
metadata <- data$process_metadata
```

---

## Deployment

### Option 1 - Run locally

Good for small surveys on your own computer or trying things out before you deploy online.

```bash
streamlit run app.py
```

Streamlit will show two URLs:
- `http://localhost:8501` — works only on your computer.
- `http://192.168.x.x:8501` — works on other devices on the same local network (e.g. your home or office Wi-Fi), but only if your firewall allows connections on port 8501.

Neither URL is accessible from the internet, so this option is not suitable for sharing with participants remotely. For a publicly accessible URL, use one of the options below.

### Option 2 - Streamlit Community Cloud (free for public repos)

This gives you a permanent public URL with no server to manage.

1. Push your repo to GitHub (your `.env` file is excluded automatically)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub repo
3. Under **Advanced settings → Secrets**, add: `OPENAI_API_KEY = "sk-..."`
4. Click **Deploy** - you get a public URL to share with participants

### Option 3 - Docker (for researchers comfortable with the command line)
The repo ships with a `Dockerfile` and `docker-compose.yml`.

**Quick start (recommended):**
```bash
docker compose up --build
```
Open [http://localhost:8501](http://localhost:8501). The container reads your `.env` file automatically.

**Without Compose:**
```bash
docker build -t surveychat .
docker run --rm -p 8501:8501 --env-file .env surveychat
```

**Production tips:**
- Remove the `volumes:` bind-mount in `docker-compose.yml` so the image is fully self-contained.
- Serve HTTPS via a reverse proxy (Caddy, nginx) in front of port 8501 - required for Qualtrics iFrame embeds.
- On a cloud VM, add `--server.port 80` to the `ENTRYPOINT` in the `Dockerfile` if you expose port 80 directly.

### Option 4 - Cloud VM (advanced)

For a permanent public deployment on a cloud server (e.g. Azure, AWS, DigitalOcean), set up a VM with Python and Docker, clone your repo, and run the app with:

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 80 --server.headless true
```

---

## Integrating with Qualtrics

For this thesis study, Qualtrics should randomize participants, store `condition_internal`, set an opaque `route_code`, launch Streamlit with that route code, and then collect the participant-visible study-data JSON in one required text-entry question. Streamlit should not persist formal research data server-side, should not expose condition labels in the participant-visible payload, and should not add posttest, mediator, manipulation-check, demographic, consent, or debrief blocks.

To embed, add a **Text / Graphic** block in Qualtrics and paste this HTML, replacing the URL with your own:

```html
<iframe
  src="https://your.apps.url/"
  width="100%"
  height="600"
  frameborder="0"
  allow="clipboard-write"
></iframe>
```

The `allow="clipboard-write"` attribute lets the built-in copy button work inside the iFrame.

**Current thesis route:**
1. In Qualtrics Survey Flow, randomize participants into the two learning orders.
2. Store researcher-facing `condition_internal` and participant-facing `route_code` as embedded data.
3. Launch Streamlit with `?route_code=${e://Field/route_code}`.
4. Immediately after Streamlit, add one required **Text Entry** question for the copy-back JSON, for example: *"Please paste the study data from the chatbot box below."*
5. Export responses and recover condition from Qualtrics embedded data, not from the participant-visible JSON.

Do not add return-URL automation, hidden-field automation, Qualtrics-side JSON validation, server-side formal data persistence, or condition labels in the participant-visible payload for the first build.

---

## Troubleshooting

**"Code not recognised"**
The passcode the participant typed does not match any `"passcode"` value in `CONDITIONS`. Check for typos in `app.py`. Passcode matching is case-insensitive, so `"alpha"` and `"ALPHA"` both work.

**"OPENAI_API_KEY not found"**
Make sure the `.env` file exists in the project folder and contains a line exactly like this (no spaces around `=`):
```
OPENAI_API_KEY=sk-your-key-here
```

**Chat returns an error message**
Verify that `API_BASE_URL` in `app.py` is set to the correct URL for your API provider, and that your key is valid and has not expired.

**The app does not open in the browser**
Manually open http://localhost:8501. If you see "connection refused", the app may have crashed - check the terminal for error messages.

**"Port 8501 already in use"**
Another instance of the app is already running. Stop it with:
```bash
pkill -f "streamlit run"
```
Or start the app on a different port:
```bash
streamlit run app.py --server.port 8502
```

**I edited `app.py` but nothing changed**
Streamlit usually reloads automatically when you save the file. If it does not, press **R** in the terminal where the app is running, or stop and restart with `streamlit run app.py`.
