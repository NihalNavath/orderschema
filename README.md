---
title: Orderschema Environment Server
emoji: 🏑
colorFrom: indigo
colorTo: gray
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---
# The Problem
![WhatsApp order example showing messy input](https://i.postimg.cc/90pRXNqG/Screenshot-2026-04-08-092206.png)

We have all ordered something through text.

A lot of businesses, especially small and medium vendors, still take orders through apps like WhatsApp, Facebook. It just makes sense almost everyone already has it (2+ billion users), it’s easy to use, and it’s completely free. For businesses, it’s the easiest way to start taking orders without forcing customers to go to some third-party website or app. Tools like WhatsApp Business are literally built for this use case, so it’s a natural choice.

But this also creates a problem. Orders come in as messy text, and someone has to sit and read everything manually. During busy times, this easily leads to mistakes — wrong items, wrong quantities, or things getting missed completely. Error rates can go as high as 20–25% in peak hours. This slows things down, puts extra pressure on staff, and leads to a bad customer experience. I’ve personally faced this a lot — getting the wrong order and then spending time fixing it is honestly frustrating.

# Orderschema Environment

OrderSchema Environment is a lightweight, real-world environment designed to convert unstructured customer messages into structured order data.

Small, medium and large businesses often rely on platforms like WhatsApp, facebook to receive orders. These messages are informal, inconsistent, and difficult to process programmatically. This environment models that exact problem and provides a way to transform messy text into clean, usable data.

The output is in json so that other developers can choose to built on top of it including automating the entire order flow.

# Example
Simple Input:
```
2 biriyani, 1x coke and pepsi please.
```
output:
```
[
  {"item": "biriyani", "quantity": 2},
  {"item": "coke", "quantity": 1},
  {"item": "pepsi", "quantity": 1}
]
```

Input
```
2 biriyani and noodles x4 coke, coke also poratta and one pepsi pls bro 😅
```

output:
```py
[
  {"item": "biriyani", "quantity": 2},
  {"item": "noodles", "quantity": 4},
  {"item": "coke", "quantity": 2},
  {"item": "poratta", "quantity": 1},
  {"item": "pepsi", "quantity": 1}
]
```

as you can see the program intelligently handles many things
- Mixed quantity formats → 2, x4, one
- Repeated items → coke, coke → merged into quantity 2
- Informal language → “pls bro 😅”
- Noisy punctuation and structure
- Implicit quantities → defaulting coke to 1 each
- converting words to numbers (four -> 4)

The above example demonstrates the system’s ability to handle noisy, informal, real-world input. It correctly interprets mixed quantity formats, merges duplicate items, ignores conversational filler, and produces clean structured data suitable for downstream automation.

## Quick Start

The simplest way to use the Orderschema environment is through the `OrderschemaEnv` class:

```python
from orderschema import OrderschemaAction, OrderschemaEnv

try:
    # Create environment from Docker image
    orderschemaenv = OrderschemaEnv.from_docker_image("orderschema-env:latest")

    # Reset
    result = orderschemaenv.reset()
    print(f"Reset: {result.observation.echoed_message}")

    # Send multiple messages
    messages = ["Hello, World!", "Testing echo", "Final message"]

    for msg in messages:
        result = orderschemaenv.step(OrderschemaAction(message=msg))
        print(f"Sent: '{msg}'")
        print(f"  → Echoed: '{result.observation.echoed_message}'")
        print(f"  → Length: {result.observation.message_length}")
        print(f"  → Reward: {result.reward}")

finally:
    # Always clean up
    orderschemaenv.close()
```

That's it! The `OrderschemaEnv.from_docker_image()` method handles:
- Starting the Docker container
- Waiting for the server to be ready
- Connecting to the environment
- Container cleanup when you call `close()`

## Building the Docker Image

Before using the environment, you need to build the Docker image:

```bash
# From project root
docker build -t orderschema-env:latest -f server/Dockerfile .
```