# Dockerized Go Game with KataGo AI

A lightweight, browser-based Go game powered by the world-class **KataGo** engine. The entire application—frontend, backend, and AI engine—is containerized using Docker for a seamless setup.

## 🧠 How It Works

The project is divided into three main components:

1. **The Frontend (HTML5 Canvas & Vanilla JS):** A lightweight, zero-dependency web interface. It draws the 19x19 Go board, captures user clicks, translates them into standard Go coordinates (e.g., "D4"), and sends the game history to the backend via a REST API.

2. **The Backend (FastAPI / Python):** A fast, modern web server. It has two jobs: serving the static HTML frontend to the user's browser, and acting as a bridge between the web API and the KataGo engine.

3. **The AI Engine (KataGo):** A highly optimized, open-source neural network built specifically for Go. The Python backend runs the KataGo binary as a background subprocess and communicates with it using the **Go Text Protocol (GTP)**. When the backend receives a move history from the frontend, it syncs the board state with KataGo, asks it to generate a move based on the selected difficulty, and returns the result to the browser.

## 🤔 Architectural Choices

- **KataGo vs. Standard Hugging Face LLMs:** Initially, one might think to use a standard text-generation model (like GPT or Llama) for AI. However, standard LLMs do not inherently understand the complex spatial strategy of Go. KataGo utilizes Monte Carlo Tree Search (MCTS) combined with a specialized neural network, making it vastly superior and genuinely competitive.

- **Docker Containerization & CI/CD:** Setting up KataGo manually requires downloading OS-specific binaries, fetching neural network weight files (`.bin.gz`), and configuring GTP settings. We use Docker to automate this. Furthermore, a GitHub Actions CI/CD pipeline automatically builds and pushes the Docker image to the GitHub Container Registry (GHCR) on every push to the `main` branch, meaning you don't even have to build the image locally.

- **FastAPI:** Chosen for its speed, simplicity, and built-in asynchronous capabilities. It effortlessly handles serving the static `index.html` while exposing the `/api/move` endpoint in a single, readable Python file.

- **Difficulty Scaling via "Visits":** Instead of swapping out entirely different models for difficulty levels, we control KataGo's strength by limiting its `maxVisits` (the number of MCTS simulations it is allowed to run before choosing a move). Less visits = faster, weaker AI; more visits = deeper thinking, stronger AI.

## 🚀 How to Run It

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your machine.
- Docker Compose (included with Docker Desktop).

### Setup & Play

1. **Create the Docker Compose file:** Create a file named `docker-compose.yml` anywhere on your machine and paste the following code:

   ```yaml
   version: '3.8'
   services:
     go-game:
       image: ghcr.io/jeroneo/go_game_browser/katago-web:latest
       container_name: katago-web
       ports:
         - "8000:8000"
       restart: unless-stopped
   ```

2. **Start the container:** Open your terminal in the same directory as your `docker-compose.yml` file and run:

   ```bash
   docker-compose up -d
   ```

   > **Note:** Docker will pull the pre-built image directly from the GitHub Container Registry.

3. **Play the game:** Open your web browser and navigate to:

   ```
   http://localhost:8000
   ```

4. **Stop the server:** When you are done playing, spin down the container by running:

   ```bash
   docker-compose down
   ```