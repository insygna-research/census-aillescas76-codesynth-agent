# The ADK API server loads each app under src/apps by importing <app>.agent and
# reading root_agent from it.
from agents.orchestrator import main_orchestrator

root_agent = main_orchestrator
