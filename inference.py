import asyncio
import json
import os
import subprocess
import textwrap
from typing import List

from openai import OpenAI

from orderschema import OrderschemaEnv, OrderschemaAction

# ---------------- CONFIG ----------------
# IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"

BENCHMARK = "orderschema"
MAX_STEPS = 1
TEMPERATURE = 0.3
MAX_TOKENS = 150

# ---------------- TASK DATA ----------------
TASKS = ["task_easy", "task_medium", "task_hard"]

TASK_DATA = {
    "task_easy": {
        "text": "biriyani 2 and chicken noodles 4",
        "target": [
            {"item": "biriyani", "quantity": 2},
            {"item": "chicken noodles", "quantity": 4},
        ],
    },
    "task_medium": {
        "text": "i need two biriyani, pepsi 2 and four chicken noodles please",
        "target": [
            {"item": "biriyani", "quantity": 2},
            {"item": "pepsi", "quantity": 2},
            {"item": "chicken noodles", "quantity": 4},
        ],
    },
    "task_hard": {
        "text": "2 biriyani and noodles x4 coke, coke also poratta and one pepsi pls bro 😅",
        "target": [
            {"item": "biriyani", "quantity": 2},
            {"item": "noodles", "quantity": 4},
            {"item": "coke", "quantity": 2},
            {"item": "poratta", "quantity": 1},
            {"item": "pepsi", "quantity": 1},
        ],
    },
}

# ---------------- PROMPT ----------------
SYSTEM_PROMPT = textwrap.dedent("""
You are a strict information extraction system.

Extract all food items and quantities.

Return ONLY JSON:
[{"item": "biriyani", "quantity": 2}]

Rules:
- NEVER return empty list if items exist
- Convert words → numbers
- Default quantity = 1
- No explanations
""").strip()


def log_start(task: str):
    print(f"[START] task={task} env={BENCHMARK} model={MODEL_NAME}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool):
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error=null",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def call_model(client: OpenAI, text: str) -> str:
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    content = completion.choices[0].message.content

    try:
        return json.dumps(json.loads(content))
    except:
        import re
        matches = re.findall(r'\[[\s\S]*?\]', content)
        for m in matches:
            try:
                return json.dumps(json.loads(m))
            except:
                continue

    return "[]"


# ---------------- MAIN ----------------
async def main():
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    for task_id in TASKS:
        prediction = "[]"
        rewards = []
        steps = 0
        score = 0.0
        success = False
        env = None

        log_start(task_id)

        try:
            task_input = TASK_DATA[task_id]
            
            if False:
                env = await OrderschemaEnv.from_docker_image(IMAGE_NAME)
            else:
                env = OrderschemaEnv(base_url=ENV_BASE_URL)
                await env.connect()
            
            await env.reset(input=task_input)
            
            text = task_input["text"]
            prediction = call_model(client, text)
            
            action = OrderschemaAction(message=prediction)
            result = await env.step(action)
            
            reward = result.reward or 0.0
            rewards.append(reward)
            steps = 1
            
            log_step(step=1, action=json.dumps({"message": prediction}), reward=reward, done=result.done)
            score = reward
            success = score > 0.5

        except Exception as e:
            print(f"[DEBUG] {e}", flush=True)

        finally:
            if env:
                await env.close()  # ← inside loop, in finally

        log_end(success=success, steps=steps, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())