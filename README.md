# Dockerized Go Game with KataGo AI

A lightweight, browser-based Go game powered by the world-class **KataGo** engine. The entire application—frontend, backend, and AI engine—is containerized using Docker for a seamless, one-command setup. Supports single-player vs. AI, local two-player, and real-time online multiplayer with integrated chat.

---

## 🧠 How It Works

The project is divided into three main components:

1. **The Frontend (HTML5 Canvas & Vanilla JS):** A lightweight, zero-dependency web interface styled after traditional Weiqi aesthetics. It draws the 19×19 Go board on an HTML5 Canvas, captures user clicks, translates them into standard GTP coordinates (e.g., `D4`), and communicates with the backend via both a REST API (for AI moves) and a WebSocket connection (for online multiplayer). The frontend enforces all core Go rules locally: captures, suicide prevention, the Ko rule, player passing, resignation, and double-pass game-over detection.

2. **The Backend (FastAPI / Python):** A fast, modern web server with three responsibilities: serving the static HTML frontend to the browser; acting as a bridge between the `/api/move` REST endpoint and the KataGo engine process; and managing stateful online multiplayer rooms via WebSocket connections, including player role assignment, game history persistence, and reconnection support.

3. **The AI Engine (KataGo):** A highly optimized, open-source neural network built specifically for Go. The Python backend runs the KataGo binary as a persistent background subprocess and communicates with it using the **Go Text Protocol (GTP)**. When the backend receives a move history, it replays the board state with `play` commands, then issues a `genmove` command to generate the next move at the requested difficulty, and returns the result to the browser.

---

## ✨ Features

### Game Modes
- **1 Player (vs AI):** Place black stones by clicking on the board. KataGo responds automatically as white.
- **2 Players (Local):** Two players share the same device and browser, taking turns on the same board.
- **2 Players (Online):** Each player connects from their own browser. The first player to open the mode receives a shareable invite link; the second player joins by following it. Color assignment (black/white) is automatic and persistent.

### Core Gameplay
- **Stone Captures:** Surrounded groups are detected and removed from the board immediately after each move, for all players and the AI, including in self-play mode.
- **Ko Rule:** The frontend tracks a fingerprint of every prior board position. Any move that would recreate a previous state is rejected with a visual error message (positional superko).
- **Suicide Prevention:** Placing a stone into a group with no remaining liberties is blocked before it is committed, in accordance with Japanese and Chinese rules.
- **Illegal Move Feedback:** Attempting an illegal move (Ko, suicide, or occupied intersection) briefly flashes a specific error message in the status panel instead of silently failing.
- **Pass Turn (虛手):** A dedicated Pass button lets the active player skip their turn. Two consecutive passes trigger automatic game-over and final scoring via `/api/score`.
- **Resign (投降):** A Resign button immediately ends the game, awarding victory to the opponent.
- **Stone Hover Preview:** A semi-transparent preview stone follows the cursor so players can see exactly where they are about to play before committing.
- **Last Move Indicator:** A small circle is drawn on the most recently played stone for at-a-glance move tracking.

### AI Features
- **AI Self-Play (觀戰模式):** Toggle spectator mode (available in 1P mode) to watch KataGo play against itself, with moves displayed every 800 ms. Consecutive passes are tracked and end the game correctly.
- **Difficulty Selection:** Three strength levels controlled by limiting KataGo's MCTS simulations (`maxVisits`):
  - **Easy** — 10 visits
  - **Medium** — 100 visits *(default)*
  - **Hard** — 500 visits
- **Locked Difficulty:** The selector locks once the first move is played and resets when starting a new game.
- **AI Resignation:** If KataGo determines the position is unwinnable, it resigns and the game ends with the correct result.

### Online Multiplayer
- **Shareable Room Links:** Selecting online mode generates a unique room URL (e.g., `?room=abc123`) that can be copied and sent to an opponent with a single click.
- **Real-Time Chat:** A live chat panel appears alongside the board in online mode, allowing both players to send messages during the game.
- **Reconnection Support:** Each browser generates a persistent, anonymous player ID stored in `localStorage`. If a player's connection drops, they can reload the page and automatically rejoin their room and color, with the full game history replayed on their board.
- **Opponent Offline Detection:** If the opponent disconnects, the game is automatically paused and a status message is shown. Play resumes the moment they reconnect.
- **Room Capacity:** Each room holds exactly two registered players. A third connection attempt is rejected with an error message.

### UI & General
- **Game Over Lock:** Once the game ends (by resignation or double pass), the board becomes inert and action buttons are disabled until a new game is started.
- **Responsive Layout:** The layout adapts across screen sizes. On wide screens the chat panel sits beside the board; on medium screens it stacks below; on mobile the entire layout wraps vertically.

---

## 🤔 Architectural Choices

- **KataGo vs. Standard LLMs:** Standard text-generation models (GPT, Llama, etc.) do not inherently understand the spatial strategy of Go. KataGo combines Monte Carlo Tree Search (MCTS) with a specialized neural network trained exclusively on Go, making it vastly superior for this task.

- **Client-Side Rule Enforcement:** KataGo enforces Go rules internally when generating moves, but it does not stream board state back to the browser. All rules are implemented directly in the frontend in pure JS. `tryPlaceStone()` simulates every player placement on a temporary copy of the board, resolves opponent captures, then checks for suicide and Ko before committing anything. AI moves and network moves go through a separate `applyConfirmedMove()` / `applyNetworkAction()` path that skips re-validation (KataGo and the server guarantee legality) but still resolves captures and records the position fingerprint. Ko detection uses positional superko: `serializeBoard()` fingerprints every board state into `boardHistory`, and any move whose resulting fingerprint already appears in that list is rejected.

- **WebSocket-Based Multiplayer:** Online multiplayer is implemented using FastAPI's native WebSocket support. A `ConnectionManager` maintains a dictionary of `RoomData` objects, each holding the two players' assigned colors, their active WebSocket connections, and the complete serialized history of moves and chat messages. All game actions (moves, passes, resigns, chat) are broadcast to both players in the room. This history is replayed on the client on reconnection, keeping both clients in sync without requiring a dedicated board-state endpoint.

- **Persistent Player Identity:** Each browser session generates a random alphanumeric player ID and stores it in `localStorage`. This ID is passed as a query parameter on every WebSocket connection (`/ws/{room_id}?player_id={id}`), enabling the server to map reconnecting clients back to their original color and room without requiring authentication.

- **Docker & CI/CD:** Setting up KataGo manually requires OS-specific binaries, neural network weight files (`.bin.gz`), and custom GTP configuration. Docker automates all of this. A GitHub Actions CI/CD pipeline automatically builds and pushes the image to GHCR on every push to `main`, so no local build is required.

- **FastAPI:** Chosen for its speed, simplicity, and async support. A single Python file serves the static `index.html`, exposes the `/api/move` and `/api/score` REST endpoints, and handles the `/ws/{room_id}` WebSocket endpoint.

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

For **online multiplayer**, select *2 Players (Online)* from the Game Mode dropdown, copy the generated invite link, and send it to your opponent. Both players need network access to the same running instance.

**4. Stop the server**

```bash
docker-compose down
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves the HTML frontend |
| `/api/move` | `POST` | Replays move history and generates the next AI move |
| `/api/score` | `POST` | Replays a finished game and computes the final score |
| `/ws/{room_id}` | `WebSocket` | Real-time multiplayer connection (accepts `?player_id=` query param) |

---

*Jérôme DO ESPIRITO SANTO — Shanghai University, 2026*