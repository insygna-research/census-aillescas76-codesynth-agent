import os
from google.adk.agents import LlmAgent
from typing import Callable

# Import necessary tools
# Assuming custom_tools is in the parent directory 'src' relative to 'src/agents'
try:
    from src.custom_tools import git_init, git_add, git_commit
except ImportError:
    # Fallback if running script directly from agents dir or structure differs
    from ..custom_tools import git_init, git_add, git_commit


# Define the tools the agent can use
versioning_tools: list[Callable] = [git_init, git_add, git_commit]

# Define the Versioning Agent
versioner_agent = LlmAgent(
    name="versioner",
    model=os.getenv("ADK_LLM_MODEL", "gemini-1.5-flash"), # Use env var or default
    instruction=(
        "Your task is to version control the generated code using Git.\n"
        "1. Read the target project directory path from session state under the key 'project_path'. This is the root directory for all Git operations.\n"
        "2. Read the list of generated/modified code paths from session state under the key 'generated_code_paths'. If this list is empty or not present, do nothing and report completion.\n"
        "3. Use the 'git_init' tool, providing the 'base_path_str' argument with the value from 'project_path'. This will initialize a repository if one doesn't exist.\n"
        "4. Use the 'git_add' tool to stage the files listed in 'generated_code_paths'. Provide the 'base_path_str' argument with the value from 'project_path' and the 'paths_to_add' argument with the list of relative paths.\n"
        "5. Use the 'git_commit' tool to commit the staged changes. Provide the 'base_path_str' argument with the value from 'project_path' and devise a suitable 'commit_message' (e.g., 'feat: Implement initial code based on requirement').\n"
        "6. Report the outcome of the Git operations (success or any errors encountered)."
    ),
    tools=versioning_tools,
    output_key="versioning_summary" # Store a summary of actions
)
