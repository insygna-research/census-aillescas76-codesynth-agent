import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

# Import sub-agent instances
# Ensure these files exist and the agent instances are correctly defined within them.
from .requirement_analysis import requirement_analyzer_agent
from .code_exploration import code_explorer_agent
from .implementation_planning import implementation_planner_agent
from .code_generation import code_generator_agent
from .code_review import code_reviewer_agent
# from .testing import tester_agent # Commented out
from .refactoring import refactorer_agent
from .versioning import versioner_agent # Import the new agent

# Placeholder agents until the real ones are created
from google.adk.agents import LlmAgent # Use LlmAgent as a placeholder type


# Configuration for the refactor loop
MAX_REFACTOR_ATTEMPTS = int(os.environ.get("MAX_REFACTOR_ATTEMPTS", 2)) # Default to 2 attempts

class RequirementImplementationOrchestrator(BaseAgent):
    """
    Orchestrates the end-to-end workflow for implementing a software requirement
    using specialized sub-agents.
    """
    def __init__(self):
        """Initializes the orchestrator with all necessary sub-agents."""
        # BaseAgent is a pydantic model: sub-agents are registered through its
        # constructor and read back from module scope, not set as attributes.
        super().__init__(sub_agents=[
            requirement_analyzer_agent,
            code_explorer_agent,
            implementation_planner_agent,
            code_generator_agent,
            code_reviewer_agent,
            # tester_agent, # Commented out
            refactorer_agent,
            versioner_agent,
        ], name="requirement_implementation_orchestrator")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Implements the custom logic for the requirement implementation workflow.
        """
        print("\n--- Starting Requirement Analysis ---")
        async for event in requirement_analyzer_agent.run_async(ctx):
            yield event
        print("--- Requirement Analysis Done ---")
        print(f"State['requirement_details']: {ctx.session.state.get('requirement_details')}")

        # Check if codebase exploration is needed
        # Use a placeholder key for now, adjust as needed based on initial input
        if ctx.session.state.get("initial_codebase_path"):
            print("\n--- Starting Code Exploration ---")
            # Pass the path to the explorer agent, potentially via state or context modification if needed
            # ctx.session.state["codebase_path"] = ctx.session.state.get("initial_codebase_path") # Example
            async for event in code_explorer_agent.run_async(ctx):
                yield event
            print("--- Code Exploration Done ---")
            print(f"State['code_context']: {ctx.session.state.get('code_context')}")
        else:
            print("\n--- Skipping Code Exploration (no initial_codebase_path provided in session state) ---")
            # Set a default context if exploration is skipped
            ctx.session.state["code_context"] = "No existing codebase provided or explored."

        print("\n--- Starting Implementation Planning ---")
        async for event in implementation_planner_agent.run_async(ctx):
            yield event
        print("--- Implementation Planning Done ---")
        print(f"State['implementation_plan']: {ctx.session.state.get('implementation_plan')}")

        print("\n--- Starting Code Generation ---")
        async for event in code_generator_agent.run_async(ctx):
            yield event
        print("--- Code Generation Done ---")
        generated_paths = ctx.session.state.get('generated_code_paths') # Get paths for check
        print(f"State['generated_code_paths']: {generated_paths}")

        # Add the Code Review Step here
        if generated_paths: # Only run review if code was generated
            print("\n--- Starting Code Review ---")
            async for event in code_reviewer_agent.run_async(ctx):
                yield event
            print("--- Code Review Done ---")
            print(f"State['code_review_summary']: {ctx.session.state.get('code_review_summary')}")
        else:
             print("\n--- Skipping Code Review: No generated code paths found. ---")

        # Add Versioning Step here
        # Check for project_path which is needed by the git tools as base_path_str
        # The versioner agent expects 'project_path' in the state. Let's ensure it's there.
        # We'll use 'codebase_path' if 'project_path' isn't explicitly set elsewhere.
        project_path_for_git = ctx.session.state.get("project_path", ctx.session.state.get("codebase_path"))

        if generated_paths and project_path_for_git: # Only run if code was generated AND project path exists
            # Ensure project_path is explicitly in the state for the versioner agent
            if "project_path" not in ctx.session.state and project_path_for_git:
                 ctx.session.state["project_path"] = project_path_for_git
                 print(f"Added 'project_path': {project_path_for_git} to session state for versioning.")

            print("\n--- Starting Versioning ---")
            async for event in versioner_agent.run_async(ctx):
                yield event
            print("--- Versioning Done ---")
            print(f"State['versioning_summary']: {ctx.session.state.get('versioning_summary')}")
        elif not generated_paths:
             print("\n--- Skipping Versioning: No generated code paths found. ---")
        else: # Implies project_path is missing
             print(f"\n--- Skipping Versioning: Project path ('project_path' or 'codebase_path') not found in session state. Searched for: {project_path_for_git} ---")


        # Ensure generated_code_paths exists before testing (Keep commented out block)
        # # if not generated_paths: # Use the variable checked above
        # #      print("\n--- Skipping Testing and Refactoring: No generated code paths found. ---")
        # #      print("\n--- Workflow Complete (Ended Early) ---")
        # #      return # Exit the workflow if no code was generated

        # # print("\n--- Starting Testing ---")
        # # # async for event in tester_agent.run_async(ctx):
        # #     yield event
        # # test_results = ctx.session.state.get("test_results", {})
        # # print("--- Testing Done ---")
        # # print(f"State['test_results']: {test_results}")

        # # --- Iterative Refactor/Test Loop ---
        # attempt = 0
        # # Check if 'status' key exists and if it's not 'PASS'
        # # Handle potential case differences and ensure status exists
        # while test_results.get("status", "UNKNOWN").upper() != "PASS" and attempt < MAX_REFACTOR_ATTEMPTS:
        #     attempt += 1
        #     print(f"\n--- Tests Failed/Errored/Unknown. Starting Refactoring Attempt {attempt}/{MAX_REFACTOR_ATTEMPTS} ---")
        #     async for event in refactorer_agent.run_async(ctx):
        #         yield event
        #     print(f"--- Refactoring Attempt {attempt} Done ---")
        #     # Assuming refactor agent updates files in place or updates 'generated_code_paths'
        #     print(f"State['generated_code_paths' after refactor]: {ctx.session.state.get('generated_code_paths')}")
        #
        #     print(f"\n--- Re-running Tests after Refactoring Attempt {attempt} ---")
        #     async for event in tester_agent.run_async(ctx): # Re-run tests
        #         yield event
        #     test_results = ctx.session.state.get("test_results", {}) # Update results
        #     print(f"--- Re-Testing Done (Attempt {attempt}) ---")
        #     print(f"State['test_results']: {test_results}")

        # # Final status check after the loop
        # if test_results.get("status", "UNKNOWN").upper() != "PASS":
        #     print(f"\n--- Warning: Tests did not pass after {attempt} refactoring attempts. Final Status: {test_results.get('status', 'UNKNOWN')} ---")
        # else:
        #     print("\n--- Tests Passed! ---")

        print("\n--- Workflow Complete ---")

# Instantiate the orchestrator agent.
# This instance will be imported by the main execution script or runner setup.
main_orchestrator = RequirementImplementationOrchestrator()
