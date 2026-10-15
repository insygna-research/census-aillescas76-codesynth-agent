"""HTTP entry point: the ADK API server over the requirement-implementation orchestrator.

Serves the standard ADK endpoints (POST /run, POST /run_sse, the session API under
/apps/codesynth/..., GET /list-apps) plus GET /health. Create a session with state
{"project_path": "<relative path>"} and send the requirement as the user message.
"""
import pathlib

from google.adk.cli.fast_api import get_fast_api_app

# Import the agent now rather than on the first request, so an agent that cannot
# load stops the container at startup instead of answering 500 for ever.
from apps.codesynth.agent import root_agent  # noqa: F401

APPS_DIR = pathlib.Path(__file__).parent / "apps"

app = get_fast_api_app(
    agents_dir=str(APPS_DIR),
    web=False,
    # Sessions live in memory: the container's filesystem is not persistent.
    use_local_storage=False,
)


@app.get("/health")
def health():
    return {"status": "ok"}
