# Copyright (c) Meta Platforms, Inc. and affiliates.

"""
Orderschema Environment (OpenEnv-compliant)

- Clean reset (no hidden task injection)
- Step follows strict contract
- Reward is deterministic and clamped to [0.01, 0.99]
"""

from uuid import uuid4
import json

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import OrderschemaAction, OrderschemaObservation
except ImportError:
    from models import OrderschemaAction, OrderschemaObservation


class OrderschemaEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._target = []

    # ---------------- RESET ----------------
    def reset(self, input=None):
        self._state = State(episode_id=str(uuid4()), step_count=0)

        if isinstance(input, dict):
            self._target = input.get("target", [])
            text = input.get("text", "")
        else:
            self._target = []
            text = ""

        return OrderschemaObservation(
            observation={"text": text},
            reward=0.0,
            done=False,
            info={}
        )

    # ---------------- STEP ----------------
    def step(self, action: OrderschemaAction) -> OrderschemaObservation:
        self._state.step_count += 1

        try:
            pred = json.loads(action.message)

            if not isinstance(pred, list):
                raise ValueError("prediction must be list")

        except Exception:
            return OrderschemaObservation(
                observation=None,
                reward=0.01,
                done=True,
                info={"error": "invalid_json", "step": self._state.step_count}
            )

        raw_reward = self._score(pred)
        reward = self._clamp_reward(raw_reward)

        return OrderschemaObservation(
            observation=pred,
            reward=reward,
            done=True,
            info={"step": self._state.step_count}
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
        if not isinstance(pred, list) or not self._target:
            return 0.0

        matched = set()

        for target_item in self._target:
            for i, pred_item in enumerate(pred):
                if i in matched:
                    continue

                if (
                    isinstance(pred_item, dict)
                    and pred_item.get("item") == target_item.get("item")
                    and pred_item.get("quantity") == target_item.get("quantity")
                ):
                    matched.add(i)
                    break

        return len(matched) / len(self._target)

    # ---------------- CLAMP ----------------
    def _clamp_reward(self, reward: float) -> float:
        """
        Clamp reward to [0.01, 0.99]
        """
        if reward <= 0.0:
            return 0.01
        if reward >= 1.0:
            return 0.99
        return float(reward)

    # ---------------- STATE ----------------
    @property
    def state(self) -> State:
        return self._state