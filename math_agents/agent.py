# Full runnable code for the StoryFlowAgent example
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import AsyncGenerator
from typing_extensions import override

from google.adk.agents import LlmAgent, BaseAgent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.events import Event
from pydantic import BaseModel, Field

# --- Constants ---
APP_NAME = "math_animation_app"
USER_ID = "12345"
SESSION_ID = "123344"
MODEL = "gemini-2.5-flash"


# INITIAL_STATE = {
#     "topic": "algebra",
#     "math_domain": "",
#     "solution": "",
#     "animation_story": "",
#     "blender_code": "",
# }


# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Custom Orchestrator Agent ---
class SupervisorAgent(BaseAgent):
    """
    Custom agent for orchestrating a workflow of math problem solving and animation.

    This agent orchestrates a sequence of LLM agents to solve a math problem.
    It uses a LoopAgent to interatively refine the solution and a SequentialAgent
    for post-processing steps like formatting and verification.
    It then delegates the task to generate animation story and blender code based on the final solution.

    """

    # --- Field Declarations for Pydantic ---
    # Declare the agents passed during initialization as class attributes with type hints
    domain_classify_agent: LlmAgent
    algebra_agent: LlmAgent
    geometry_agent: LlmAgent
    calculus_agent: LlmAgent
    probability_agent: LlmAgent
    trigonometry_agent: LlmAgent
    statistics_agent: LlmAgent
    animation_agent: LlmAgent
    blender_code_agent: LlmAgent

    # loop_agent: LoopAgent
    sequential_agent: SequentialAgent

    # model_config allows setting Pydantic configurations if needed, e.g., arbitrary_types_allowed
    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        domain_classify_agent: LlmAgent,
        algebra_agent: LlmAgent,
        geometry_agent: LlmAgent,
        calculus_agent: LlmAgent,
        probability_agent: LlmAgent,
        trigonometry_agent: LlmAgent,
        statistics_agent: LlmAgent,
        animation_agent: LlmAgent,
        blender_code_agent: LlmAgent,
    ):
        """
        Initializes the SupervisorAgent.

        Args:
            name: The name of the agent.
            domain_classify_agent: An LlmAgent for classifying the math problem domain.
            algebra_agent: An LlmAgent for algebra problems.
            geometry_agent: An LlmAgent for geometry problems.
            calculus_agent: An LlmAgent for calculus problems.
            probability_agent: An LlmAgent for probability problems.
            trigonometry_agent: An LlmAgent for trigonometry problems.
            statistics_agent: An LlmAgent for statistics problems.
            animation_agent: An LlmAgent for animation tasks.
            blender_code_agent: An LlmAgent for Blender code generation.
        """
        # Create internal agents *before* calling super().__init__
        # loop_agent = LoopAgent(
        #     name="CriticReviserLoop", sub_agents=[critic, reviser], max_iterations=2
        # )
        sequential_agent = SequentialAgent(
            name="PostProcessing", sub_agents=[animation_agent, blender_code_agent]
        )

        # Define the sub_agents list for the framework
        sub_agents_list = [
            domain_classify_agent,
            algebra_agent,
            geometry_agent,
            calculus_agent,
            probability_agent,
            trigonometry_agent,
            statistics_agent,
            # animation_agent,
            # blender_code_agent,
            sequential_agent,
        ]

        # Pydantic will validate and assign them based on the class annotations.
        super().__init__(
            name=name,
            domain_classify_agent=domain_classify_agent,
            algebra_agent=algebra_agent,
            geometry_agent=geometry_agent,
            calculus_agent=calculus_agent,
            probability_agent=probability_agent,
            trigonometry_agent=trigonometry_agent,
            statistics_agent=statistics_agent,
            animation_agent=animation_agent,
            blender_code_agent=blender_code_agent,
            sequential_agent=sequential_agent,
            sub_agents=sub_agents_list, # Pass the sub_agents list directly
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implements the custom orchestration logic for the math problem-solving and animation workflow.
        Uses the instance attributes assigned by Pydantic (e.g., self.story_generator).
        """
        logger.info(f"[{self.name}] Starting math problem-solving workflow.")
        logger.info(f"[{self.name}] Current session state at start: {ctx.session.state}")

        # Extract the topic from session state
        if not "topic" in ctx.session.state:
            if ctx.user_content and ctx.user_content.parts:
                ctx.session.state["topic"] = ctx.user_content.parts[0].text
                logger.info(f"[{self.name}] Extracted topic from user content: {ctx.session.state['topic']}")
            else:
                logger.error(f"[{self.name}] No topic found in session state or user content. Aborting.")
                return

        # topic = ctx.session.state["topic"]
        # logger.info(f"[{self.name}] Problem topic: {topic}")

        # Ensure topic exists in state
        if "topic" not in ctx.session.state or not ctx.session.state["topic"]:
            logger.error(f"[{self.name}] No topic found in session state. Aborting.")
            return
        

        # 1. Initialize domain classify agent
        async for event in self.domain_classify_agent.run_async(ctx):
            logger.info(f"[{self.name}] Event from DomainClassifyAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
            yield event

        if "math_domain" not in ctx.session.state or not ctx.session.state["math_domain"]:
            logger.error(f"[{self.name}] Math domain classification failed. Aborting.")
            return
        
        logger.info(f"[{self.name}] Classified math domain: {ctx.session.state['math_domain']}")
        
        # 2. if the domain is algebra, call the algebra agent
        # if domain is geometry, call the geometry agent, and so on.
        domain = ctx.session.state.get("math_domain")

        logger.info(f"[{self.name}] Running SupervisorAgent...")
        if domain == "algebra":
            async for event in self.algebra_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from AlgebraAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        elif domain == "geometry":
            async for event in self.geometry_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from GeometryAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        elif domain == "calculus":
            async for event in self.calculus_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from CalculusAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        elif domain == "probability":
            async for event in self.probability_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from ProbabilityAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        elif domain == "trigonometry":
            async for event in self.trigonometry_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from TrigonometryAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        elif domain == "statistics":
            async for event in self.statistics_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from StatisticsAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event

        # 3. Once the solution is obtained, proceed to animation and blender code generation. The solution is expected to be in ctx.session.state["solution"]
        solution = ctx.session.state.get("solution")
        logger.info(f"[{self.name}] Solution obtained: {solution}")

        # 4. call animation agent and blender code agent, These agents run sequentially. they take the solution as input and generate animation story and blender code respectively.
        async for event in self.animation_agent.run_async(ctx):
            logger.info(f"[{self.name}] Event from AnimationAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
            yield event

        async for event in self.blender_code_agent.run_async(ctx):
            logger.info(f"[{self.name}] Event from BlenderCodeAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
            yield event
        # 5. Finally, run the sequential post-processing agent
        async for event in self.sequential_agent.run_async(ctx):
            logger.info(f"[{self.name}] Event from SequentialAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
            yield event

# --- Define the individual LLM agents ---

domain_classify_agent = LlmAgent(
    name="DomainClassifyAgent",
    model=MODEL,
    instruction="""You are a math domain classifier. Given the following problem statement: {{topic}}, classify it into one of the following domains: algebra, geometry, calculus, trigonometry, probability, statistics. Respond with only the domain name.""",
    input_schema=None,
    output_key="math_domain",  # Key for storing output in session state
)

algebra_agent = LlmAgent(
    name="AlgebraAgent",
    model=MODEL,
    instruction="""You are a math problem solver. Solve the following algebra problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution",  # Key for storing output in session state
)

geometry_agent = LlmAgent(
    name="GeometryAgent",
    model=MODEL,
    instruction="""You are a geometry problem solver. Solve the following geometry problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution",  # Key for storing output in session state
)

calculus_agent = LlmAgent(
    name="CalculusAgent",
    model=MODEL,
    instruction="""You are a calculus problem solver. Solve the following calculus problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution",  # Key for storing output in session state
)

trigonometry_agent = LlmAgent(
    name="TrigonometryAgent",
    model=MODEL,
    instruction="""You are a trigonometry problem solver. Solve the following trigonometry problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution",
)

probability_agent = LlmAgent(
    name="ProbabilityAgent",
    model=MODEL,
    instruction="""You are a probability problem solver. Solve the following probability problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution", # Key for storing output in session state
)

statistics_agent = LlmAgent(
    name="StatisticsAgent",
    model=MODEL,
    instruction="""You are a statistics problem solver. Solve the following statistics problem: {{topic}}. Provide a step-by-step solution.""",
    input_schema=None,
    output_key="solution",  # Key for storing output in session state
)

animation_agent = LlmAgent(
    name="AnimationAgent",
    model=MODEL,
    instruction="""You are an expert story generator for animations. Based on the math solution provided: {solution}, generate a creative story outline for an animation that illustrates the solution.""",
    input_schema=None,
    output_key="animation_story",  # Key for storing output in session state
)

blender_code_agent = LlmAgent(
    name="BlenderCodeAgent",
    model=MODEL,
    instruction="""You generate Blender 4.4.3+ Python scripts for math animations.

Strict rules:
- Do NOT use bpy.ops.* or bpy.context.* selection-dependent patterns (e.g., active_object).
- Use explicit datablock creation via bpy.data.*.new() and link with scene.collection.objects.link(obj), or a created child collection.
- Idempotency: check for existing datablocks by name before creating. Remove or reuse safely.
- Encapsulate all logic in main(), and call it with if __name__ == "__main__":.
- Provide helper functions: ensure_collection(name), link_object(obj, collection=None), clean_scene().
- Reference objects via variables or names; never rely on UI selection.
- Set render and frame ranges explicitly; avoid defaults.
- Output ONLY a single Python script inside one code block.

Inputs:
- Use session state 'solution' and 'animation_story' for semantic guidance.
- Derive clear naming: prefix objects/materials with a stable scene tag (e.g., 'Anim_' or domain-specific).
""",
    input_schema=None,
    output_key="blender_code",
)





# --- Create the custom agent instance ---
root_agent = SupervisorAgent(
    name="SupervisorAgent",
    domain_classify_agent=domain_classify_agent,
    algebra_agent=algebra_agent,
    geometry_agent=geometry_agent,
    calculus_agent=calculus_agent,
    trigonometry_agent=trigonometry_agent,
    probability_agent=probability_agent,
    statistics_agent=statistics_agent,
    animation_agent=animation_agent,
    blender_code_agent=blender_code_agent,
)

# INITIAL_STATE = {"topic": "user_topic"}

# --- Setup Runner and Session ---
# async def setup_session_and_runner():
#     session_service = InMemorySessionService()
#     session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID, state=INITIAL_STATE)
#     logger.info(f"Initial session state: {session.state}")
#     runner = Runner(
#         agent=root_agent, # Pass the custom orchestrator agent
#         app_name=APP_NAME,
#         session_service=session_service
#     )
#     return session_service, runner


INITIAL_STATE = {
    "topic": "",
    "math_domain": "",
    "solution": "",
    "animation_story": "",
    "blender_code": "",
}

async def setup_session_and_runner(initial_topic: str = ""):
    session_service = InMemorySessionService()
    initial_state = dict(INITIAL_STATE)
    initial_state["topic"] = initial_topic or ""
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=initial_state,
    )
    logger.info(f"Initial session state: {session.state}")
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    return session_service, runner

# --- Function to Interact with the Agent ---

async def call_agent_async(user_input_topic: str):
    logger.info("=== Starting call_agent_async ===")
    logger.info(f"User input topic: {user_input_topic}")

    # Pass the question into setup so it's stored in session.state["topic"]
    session_service, runner = await setup_session_and_runner(initial_topic=user_input_topic)

    current_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    if not current_session:
        logger.error("Session not found!")
        return

    logger.info(f"Session state immediately after setup: {current_session.state}")

    # Ensure topic is set and other keys exist
    current_session.state["topic"] = user_input_topic
    for key in ["math_domain", "solution", "animation_story", "blender_code"]:
        current_session.state.setdefault(key, "")

    await session_service.update_session(current_session)
    logger.info(f"Session state after update: {current_session.state}")

    content = types.Content(
        role="user",
        parts=[types.Part(text=f"Please solve and animate: {user_input_topic}")]
    )

    events = runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=content,
    )

    final_response = "No final response captured."
    async for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print("\n--- Agent Interaction Result ---")
    print("Agent Final Response: ", final_response)

    final_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    print("Final Session State:")
    import json
    print(json.dumps(final_session.state, indent=2))
    print("-------------------------------\n")



# --- Run the Agent ---
# Note: In Colab, you can directly use 'await' at the top level.
# If running this code as a standalone Python script, you'll need to use asyncio.run() or manage the event loop.
if __name__ == "__main__":
    import asyncio
    user_topic = "Solve (a+b)^2 and create an animation illustrating the solution."
    asyncio.run(call_agent_async(user_topic))