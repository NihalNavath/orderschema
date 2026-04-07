try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

from fastapi import Request

import sys
import os

# ensure parent dir is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import OrderschemaAction, OrderschemaObservation
from server.orderschema_environment import OrderschemaEnvironment


# ---------------- TASK DATA ----------------
TASKS = {
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

app = create_app(
    OrderschemaEnvironment,
    OrderschemaAction,
    OrderschemaObservation,
    env_name="orderschema",
    max_concurrent_envs=1,
)

@app.get("/tasks")
async def get_tasks():
    return {
        "tasks": [
            {
                "id": task_id,
                "input": {
                    "text": task["text"],
                    "target": task["target"],
                },
            }
            for task_id, task in TASKS.items()
        ]
    }


@app.post("/grader")
async def grade(request: Request):
    body = await request.json()

    target = body.get("target", [])
    pred = body.get("prediction", [])

    if not isinstance(pred, list):
        return {
            "reward": 0.01,
            "info": {"error": "invalid_prediction"},
        }

    matched = set()

    for t in target:
        for i, p in enumerate(pred):
            if i in matched:
                continue

            if (
                isinstance(p, dict)
                and p.get("item") == t.get("item")
                and p.get("quantity") == t.get("quantity")
            ):
                matched.add(i)
                break

    raw_reward = len(matched) / len(target) if target else 0.0

    # clamp to [0.01, 0.99]
    if raw_reward <= 0.0:
        reward = 0.01
    elif raw_reward >= 1.0:
        reward = 0.99
    else:
        reward = float(raw_reward)

    return {
        "reward": reward,
        "info": {
            "matched": len(matched),
            "total": len(target),
        },
    }


# ---------------- MAIN ----------------
def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()