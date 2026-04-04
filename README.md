# Dockerized Go Game with KataGo AI

A lightweight, browser-based Go game powered by the world-class **KataGo** engine. The entire application—frontend, backend, and AI engine—is containerized using Docker for a seamless, one-command setup.

---

## 🧠 How It Works

The project is divided into three main components:

1. **The Frontend (HTML5 Canvas & Vanilla JS):** A lightweight, zero-dependency web interface styled after traditional Weiqi aesthetics. It draws the 19×19 Go board on an HTML5 Canvas, captures user clicks, translates them into standard GTP coordinates (e.g., `D4`), and sends the full game history to the backend via a REST API call. The frontend enforces all core Go rules locally: captures, suicide prevention, the Ko rule, player passing, and double-pass game-over detection.

2. **The Backend (FastAPI / Python):** A fast, modern web server with two responsibilities: serving the static HTML frontend to the browser, and acting as a bridge between the `/api/move` REST endpoint and the KataGo engine process.

3. **The AI Engine (KataGo):** A highly optimized, open-source neural network built specifically for Go. The Python backend runs the KataGo binary as a persistent background subprocess and communicates with it using the **Go Text Protocol (GTP)**. When the backend receives a move history, it replays the board state with `play` commands, then issues a `genmove` command to generate the next move at the requested difficulty, and returns the result to the browser.

---

## ✨ Features

- **Play vs. AI:** Place black stones by clicking on the board. KataGo responds automatically as white.
- **Stone Captures:** Surrounded groups are detected and removed from the board immediately after each move, for both the player and the AI, including in self-play mode.
- **Ko Rule:** The frontend tracks a fingerprint of every prior board position. Any move that would recreate a previous state is rejected with a visual error message (positional superko).
- **Suicide Prevention:** Placing a stone into a group with no remaining liberties is blocked before it is committed, in accordance with Japanese and Chinese rules.
- **Illegal Move Feedback:** Attempting an illegal move (Ko, suicide, or occupied intersection) briefly flashes a specific error message in the status panel instead of silently failing.
- **Pass Turn (虛手):** A dedicated Pass button lets the player skip their turn. Two consecutive passes (player then AI, or vice versa) trigger automatic game-over and final scoring.
- **AI Self-Play (觀戰模式):** Toggle spectator mode to watch KataGo play against itself, with moves displayed every 600 ms. Consecutive passes are tracked and end the game correctly.
- **Difficulty Selection:** Three strength levels controlled by limiting KataGo's MCTS simulations (`maxVisits`):
  - **Easy** — 10 visits
  - **Medium** — 100 visits *(default)*
  - **Hard** — 500 visits
- **Locked Difficulty:** The selector locks once the first move is played and resets when starting a new game.
- **Game Over Lock:** Once the game ends (by resignation or double pass), the board becomes inert and the Pass button is disabled until a new game is started.

---

## 🤔 Architectural Choices

- **KataGo vs. Standard LLMs:** Standard text-generation models (GPT, Llama, etc.) do not inherently understand the spatial strategy of Go. KataGo combines Monte Carlo Tree Search (MCTS) with a specialized neural network trained exclusively on Go, making it vastly superior for this task.

- **Client-Side Rule Enforcement:** KataGo enforces Go rules internally when generating moves, but it does not stream board state back to the browser. Rather than adding a dedicated `/api/board` endpoint and an extra round-trip per move, all rules are implemented directly in the frontend in pure JS. `tryPlaceStone()` simulates every player placement on a temporary copy of the board, resolves opponent captures, then checks for suicide and Ko before committing anything. AI moves go through a separate `applyAIMove()` path that skips validation (KataGo guarantees legality) but still resolves captures and records the position. Ko detection uses positional superko: `serializeBoard()` fingerprints every board state into `boardHistory`, and any move whose resulting fingerprint already appears in that list is rejected.

- **Docker & CI/CD:** Setting up KataGo manually requires OS-specific binaries, neural network weight files (`.bin.gz`), and custom GTP configuration. Docker automates all of this. A GitHub Actions CI/CD pipeline automatically builds and pushes the image to GHCR on every push to `main`, so no local build is required.

- **FastAPI:** Chosen for its speed, simplicity, and async support. A single Python file serves the static `index.html` and exposes the `/api/move` endpoint.

- **Difficulty via `maxVisits`:** Rather than swapping models, KataGo's strength is tuned by capping the number of MCTS simulations per move. Fewer visits = faster, weaker play; more visits = deeper search, stronger play.

---

## 🚀 How to Run It

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your machine.
- Docker Compose (included with Docker Desktop).

### Setup & Play

**1. Create the Docker Compose file**

Create a file named `docker-compose.yml` anywhere on your machine and paste the following:

```yaml
version: '3.8'
services:
  go-game:
    image: ghcr.io/jeroneo/katago-web:latest
    container_name: katago-web
    ports:
      - "8000:8000"
    restart: unless-stopped
```

**2. Start the container**

```bash
docker-compose up -d
```

> Docker will pull the pre-built image directly from GHCR — no local build needed.

**3. Play the game**

Open your browser and navigate to `http://localhost:8000`.

**4. Stop the server**

```bash
docker-compose down
```

---

*Jérôme DO ESPIRITO SANTO — Shanghai University, 2026*