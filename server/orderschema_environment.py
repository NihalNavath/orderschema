# Copyright (c) Meta Platforms, Inc. and affiliates.

"""
Orderschema Environment Implementation.
"""
from uuid import uuid4
import json

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import OrderschemaAction, OrderschemaObservation
    from ..parser import parse_order
except ImportError:
    from models import OrderschemaAction, OrderschemaObservation
    from parser import parse_order

TASK_DATA = {
    "task_easy": {
        "text": "biriyani 2 and chicken noodles 4",
        "target": [
            {"item": "biriyani", "quantity": 2},
            {"item": "chicken noodles", "quantity": 4},
        ],
        "note": "Clear structure with explicit quantity-item pairs",
    },

    "task_medium": {
        "text": "i need two biriyani, pepsi 2 and four chicken noodles please",
        "target": [
            {"item": "biriyani", "quantity": 2},
            {"item": "pepsi", "quantity": 2},
            {"item": "chicken noodles", "quantity": 4},
        ],
        "note": "Handles word numbers, filler text, and mixed formats",
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
        "note": "Ambiguity + noise: mixed separators, duplicate aggregation, implicit quantity (poratta), informal language",
    },
}


class OrderschemaEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.target = []
        self.messy_text = ""

    def reset(self) -> OrderschemaObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)

        task_id = getattr(self._state, "task_id", None)

        # 🔥 fallback for local runs
        if task_id is None:
            if not hasattr(self, "_task_index"):
                self._task_index = 0

            task_ids = ["task_easy", "task_medium", "task_hard"]

            task_id = task_ids[self._task_index % len(task_ids)]
            self._task_index += 1

        task = TASK_DATA[task_id]

        print("TASK:", task_id, "| TARGET:", task["target"])

        self.messy_text = task["text"]
        self.target = task["target"]

        return OrderschemaObservation(
            echoed_message=self.messy_text,
            message_length=len(self.messy_text),
            target=self.target,
            prediction=[],
            done=False,
            reward=0.0,
        )

    def step(self, action: OrderschemaAction) -> OrderschemaObservation:  # type: ignore[override]
        self._state.step_count += 1

        try:
            pred = json.loads(action.message)
            # treat empty as failure
            if not pred:
                raise ValueError("empty prediction")

            source = "model"

        except Exception:
            try:
                pred = parse_order(self.messy_text)
                source = "fallback_parser"
            except Exception:
                return OrderschemaObservation(
                    echoed_message=self.messy_text,
                    message_length=len(self.messy_text),
                    target=self.target,
                    prediction=[],
                    done=True,
                    reward=0.0,
                    error="both_failed",
                )

        reward = self._score(pred)

        return OrderschemaObservation(
            echoed_message=self.messy_text,
            message_length=len(self.messy_text),
            target=self.target,
            prediction=pred,
            done=True,
            reward=reward,
            error=None,
            metadata={
                "step": self._state.step_count,
                "source": source,
            },
        )

    def _score(self, pred):
        """
            Compute a normalized reward score for the predicted order items.

            This function evaluates how closely the predicted list of items matches
            the ground truth (`self.target`). The reward is a float in the range [0.0, 1.0].

            Scoring Rules:
            - Each ground truth item is matched against at most one predicted item.
            - A match requires:
                - Exact string match of the "item" field
                - Exact integer match of the "quantity" field
            - Each correctly matched (item, quantity) pair contributes +1 to the score.
            - Predicted items cannot be reused for multiple matches (no double counting).

            Normalization:
            - Final reward = (number of correct matches) / (total number of target items)

            Edge Cases:
            - If `pred` is not a list → reward = 0.0
            - If `self.target` is empty → reward = 0.0
            - Extra predicted items (not in target) are penalized
            - Missing target items reduce the score proportionally

            Examples:
            - Perfect match:
                target = 2 items, pred matches both → reward = 1.0
            - Partial match:
                target = 4 items, pred matches 2 → reward = 0.5
            - No match:
                target = 3 items, pred matches none → reward = 0.0

            This scoring method provides partial credit while ensuring strict correctness
            for both item identity and quantity.
        """
        if not isinstance(pred, list):
            return 0.0

        matched = set()

        for target_item in self.target:
            for i, pred_item in enumerate(pred):
                if i in matched:
                    continue

                if (
                    isinstance(pred_item, dict)
                    and pred_item.get("item") == target_item["item"]
                    and pred_item.get("quantity") == target_item["quantity"]
                ):
                    matched.add(i)
                    break

        return len(matched) / len(self.target) if self.target else 0.0

    @property
    def state(self) -> State:
        return self._state