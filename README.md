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

## Deploying to Hugging Face Spaces

You can easily deploy your OpenEnv environment to Hugging Face Spaces using the `openenv push` command:

```bash
# From the environment directory (where openenv.yaml is located)
openenv push

# Or specify options
openenv push --namespace my-org --private
```

The `openenv push` command will:
1. Validate that the directory is an OpenEnv environment (checks for `openenv.yaml`)
2. Prepare a custom build for Hugging Face Docker space (enables web interface)
3. Upload to Hugging Face (ensuring you're logged in)

### Prerequisites

- Authenticate with Hugging Face: The command will prompt for login if not already authenticated

### Options

- `--directory`, `-d`: Directory containing the OpenEnv environment (defaults to current directory)
- `--repo-id`, `-r`: Repository ID in format 'username/repo-name' (defaults to 'username/env-name' from openenv.yaml)
- `--base-image`, `-b`: Base Docker image to use (overrides Dockerfile FROM)
- `--private`: Deploy the space as private (default: public)

### Examples

```bash
# Push to your personal namespace (defaults to username/env-name from openenv.yaml)
openenv push

# Push to a specific repository
openenv push --repo-id my-org/my-env

# Push with a custom base image
openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Push as a private space
openenv push --private

# Combine options
openenv push --repo-id my-org/my-env --base-image custom-base:latest --private
```

After deployment, your space will be available at:
`https://huggingface.co/spaces/<repo-id>`

The deployed space includes:
- **Web Interface** at `/web` - Interactive UI for exploring the environment
- **API Documentation** at `/docs` - Full OpenAPI/Swagger interface
- **Health Check** at `/health` - Container health monitoring
- **WebSocket** at `/ws` - Persistent session endpoint for low-latency interactions

## Environment Details

### Action
**OrderschemaAction**: Contains a single field
- `message` (str) - The message to echo back

### Observation
**OrderschemaObservation**: Contains the echo response and metadata
- `echoed_message` (str) - The message echoed back
- `message_length` (int) - Length of the message
- `reward` (float) - Reward based on message length (length × 0.1)
- `done` (bool) - Always False for echo environment
- `metadata` (dict) - Additional info like step count