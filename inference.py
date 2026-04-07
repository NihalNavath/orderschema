"""
Inference Script Example
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME The name of the local image to use for the environment if you are using from_docker_image()
                     method

- Defaults are set only for API_BASE_URL and MODEL_NAME 
    (and should reflect your active inference setup):
    API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-endpoint>")
    MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model>")
    
- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
    - Each tasks should return score in [0, 1]

  Example:
    [START] task=click-test env=miniwob model=Qwen3-VL-30B
    [STEP] step=1 action=click('123') reward=0.00 done=false error=null
    [STEP] step=2 action=fill('456','text') reward=0.00 done=false error=null
    [STEP] step=3 action=click('789') reward=1.00 done=true error=null
    [END] success=true steps=3 score=1.00 rewards=0.00,0.00,1.00
"""

import asyncio
import json
import os
import textwrap
from typing import List, Optional

from openai import OpenAI

from orderschema import OrderschemaEnv, OrderschemaAction, OrderschemaObservation

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or "orderschema"
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
TASK_NAME = os.getenv("SORTLY_TASK", "order_parsing")
BENCHMARK = os.getenv("SORTLY_BENCHMARK", "orderschema")
MAX_STEPS = 3
TEMPERATURE = 0.7
MAX_TOKENS = 150
SUCCESS_SCORE_THRESHOLD = 0.1  # normalized score in [0, 1]

# Max possible reward is 1.0 since it is one-shot
_MAX_REWARD_PER_STEP = 1.0
MAX_TOTAL_REWARD = 1.0

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a strict information extraction system.

    Task:
    Extract all food items and their quantities from the input text.

    Output:
    Return ONLY a valid JSON array like:
    [{"item": "biriyani", "quantity": 2}]

    Rules:
    - NEVER return an empty list if any items exist
    - Convert number words to digits (e.g., "four" → 4)
    - Combine words correctly (e.g., "chicken noodles")
    - If no quantity is given, default to 1
    - Do NOT include any explanation, text, or markdown
    - Output ONLY JSON
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def build_user_prompt(step: int, last_output: str, last_reward: float, history: List[str]) -> str:
    return f"""
            Extract all items and their quantities from the text below.

            Text:
            {last_output}

            Output rules:
            - Return ONLY a JSON array
            - Format: [{{"item": "...", "quantity": number}}]
            - Convert words like "four" → 4
            - If quantity is missing, use 1
            - NEVER return an empty list if items exist
            - No explanations, no markdown, no extra text

            JSON:
            """.strip()


def get_model_message(client: OpenAI, step: int, last_output: str, last_reward: float, history: List[str]) -> OrderschemaAction:
    user_prompt = build_user_prompt(step, last_output, last_reward, history)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        content = completion.choices[0].message.content

        import json
        import re

        parsed_json = None

        # 1. Try direct parse
        try:
            parsed_json = json.loads(content)
        except Exception:
            pass

        # 2. Extract JSON array if wrapped in text
        if parsed_json is None:
            matches = re.findall(r'\[[\s\S]*?\]', content)
            for m in matches:
                try:
                    parsed_json = json.loads(m)
                    break
                except Exception:
                    continue

        if parsed_json is None:
            parsed_json = []

        if not isinstance(parsed_json, list):
            parsed_json = []

        message_str = json.dumps(parsed_json)

        return OrderschemaAction(
            message=message_str
        )

    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return OrderschemaAction(message="[]")


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    env = await OrderschemaEnv.from_docker_image(LOCAL_IMAGE_NAME)

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    TASK_IDS = ["task_easy", "task_medium", "task_hard"]

    try:
        for episode in range(MAX_STEPS):
            result = await env.reset()

            last_output = result.observation.echoed_message
            last_reward = 0.0

            action = get_model_message(
                client,
                episode + 1,
                last_output,
                last_reward,
                history
            )

            result = await env.step(
                OrderschemaAction(message=action.message)
            )

            obs = result.observation
            reward = result.reward or 0.0
            done = result.done
            error = None

            rewards.append(reward)
            steps_taken += 1

            action_str = json.dumps({"message": action.message})

            log_step(
                step=episode + 1,
                action=action_str,
                reward=reward,
                done=done,
                error=error
            )

            history.append(
                f"Episode {episode+1}: {action_str!r} -> reward {reward:+.2f}"
            )

        score = sum(rewards) / MAX_TOTAL_REWARD if MAX_TOTAL_REWARD > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error (container cleanup): {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())