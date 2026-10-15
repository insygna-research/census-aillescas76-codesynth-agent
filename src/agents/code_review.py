import os
from google.adk.agents import LlmAgent
from typing import Callable

# Import necessary tools
# Adjust the import path based on your project structure
from src.custom_tools import read_file # Ensure this import is present and correct

# Define the tools the agent can use
code_review_tools: list[Callable] = [read_file] # Add read_file here

# Define the Code Review Agent
code_reviewer_agent = LlmAgent(
    name="code_reviewer",
    model=os.getenv("ADK_LLM_MODEL", "gemini-1.5-flash"), # Use env var or default
    instruction=(
        "Your task is to review the generated code based on the implementation plan and general coding standards.\n"
        "1. Review the implementation plan provided in session state under the key 'implementation_plan'.\n"
        "2. Review the list of generated code paths provided in session state under the key 'generated_code_paths'. These paths are relative to the project path.\n"
        "3. Read the target project directory path from session state under the key 'project_path'. This is the root directory where the generated code resides.\n"
        "4. Use the 'read_file' tool to examine the content of each generated file listed in 'generated_code_paths'. When calling 'read_file', you MUST provide the 'base_path_str' argument with the value from 'project_path', and the 'path' argument must be the relative path of the file (from 'generated_code_paths').\n"
        "5. Evaluate the code for:\n"
        "    - Adherence to the implementation plan.\n"
        "    - Correctness and potential bugs.\n"
        "    - Readability, clarity, and style (e.g., variable names, comments, structure).\n"
        "    - Adherence to standard Python best practices (PEP 8).\n"
        "6. Provide a concise summary of your findings, highlighting any major issues or areas for improvement.\n"
        "7. Store your review summary in the session state under the key 'code_review_summary'."
    ),
    tools=code_review_tools, # Ensure this uses the list defined above
    # Add temperature or other model parameters if needed
    # temperature=0.7,
)
