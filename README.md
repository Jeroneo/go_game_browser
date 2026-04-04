# Dockerized Go Game with KataGo AI

A lightweight, browser-based Go game powered by the world-class **KataGo** engine. The entire application—frontend, backend, and AI engine—is containerized using Docker for a seamless, one-command setup.

---

## 🧠 How It Works

The project is divided into three main components:

1. **The Frontend (HTML5 Canvas & Vanilla JS):** A lightweight, zero-dependency web interface styled after traditional Weiqi aesthetics. It draws the 19×19 Go board on an HTML5 Canvas, captures user clicks, translates them into standard GTP coordinates (e.g., `D4`), and sends the full game history to the backend via a REST API call. The frontend also enforces Go rules locally: after every stone placement it runs a capture detection pass and removes any surrounded groups from the board state before redrawing.

2. **The Backend (FastAPI / Python):** A fast, modern web server with two responsibilities: serving the static HTML frontend to the browser, and acting as a bridge between the `/api/move` REST endpoint and the KataGo engine process.

3. **The AI Engine (KataGo):** A highly optimized, open-source neural network built specifically for Go. The Python backend runs the KataGo binary as a persistent background subprocess and communicates with it using the **Go Text Protocol (GTP)**. When the backend receives a move history, it replays the board state with `play` commands, then issues a `genmove` command to generate the next move at the requested difficulty, and returns the result to the browser.

---

## ✨ Features

- **Play vs. AI:** Place black stones by clicking on the board. KataGo responds automatically as white.
- **Stone Captures:** Surrounded groups are detected and removed from the board immediately after each move, for both the player and the AI, including in self-play mode.
- **AI Self-Play (觀戰模式):** Toggle spectator mode to watch KataGo play against itself, with moves displayed every 600 ms.
- **Difficulty Selection:** Three strength levels controlled by limiting KataGo's MCTS simulations (`maxVisits`):
  - **Easy** — 10 visits
  - **Medium** — 100 visits *(default)*
  - **Hard** — 500 visits
- **Locked Difficulty:** The selector locks once the first move is played and resets when starting a new game.
- **Game Over Lock:** Once the game ends (by pass or resignation), the board becomes inert — no further stones can be placed until a new game is started.

---

## 🤔 Architectural Choices

- **KataGo vs. Standard LLMs:** Standard text-generation models (GPT, Llama, etc.) do not inherently understand the spatial strategy of Go. KataGo combines Monte Carlo Tree Search (MCTS) with a specialized neural network trained exclusively on Go, making it vastly superior for this task.

- **Client-Side Capture Logic:** KataGo enforces Go rules internally when generating moves, but it does not stream board state back to the browser. Rather than adding a separate `/api/board` endpoint and an extra round-trip per move, capture detection is implemented directly in the frontend using three pure JS functions — `getNeighbors`, `getGroup`, and `getLiberties`. After any stone is placed, all opponent groups with zero liberties are deleted from `boardState` before the canvas is redrawn. The suicide rule (placing into a group with no liberties) is also handled.

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
