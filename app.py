from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
import subprocess
import threading
import time
import json

app = FastAPI()

# ---------------------------------------------------------
# KataGo GTP Integration
# ---------------------------------------------------------
KATAGO_CMD = [
    "./katago", "gtp",
    "-model", "model.bin.gz",
    "-config", "gtp_config.cfg"
]

# Lock to ensure only one GTP command is in-flight at a time.
katago_lock = threading.Lock()
katago_process = None


def start_katago() -> subprocess.Popen:
    """Spawns a fresh KataGo subprocess and returns it."""
    print("Starting KataGo engine...")
    proc = subprocess.Popen(
        KATAGO_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    time.sleep(2)  # Give KataGo time to load the neural network

    if proc.poll() is not None:
        error_output = proc.stderr.read()
        print("========================================")
        print("FATAL ERROR: KataGo crashed on startup!")
        print(error_output)
        print("========================================")

    return proc


def get_katago() -> subprocess.Popen:
    """Returns a live KataGo process, restarting it if it has crashed."""
    global katago_process
    if katago_process is None or katago_process.poll() is not None:
        print("KataGo is not running — restarting...")
        katago_process = start_katago()
    return katago_process


def send_gtp_command(command: str) -> str:
    """Sends a GTP command to KataGo and reads the response. Thread-safe."""
    with katago_lock:
        proc = get_katago()
        proc.stdin.write(command + "\n")
        proc.stdin.flush()

        response = ""
        while True:
            line = proc.stdout.readline()
            if line == "":
                raise ValueError("KataGo engine stopped responding.")
            if line == "\n":
                if response != "":
                    break
                else:
                    continue
            response += line

    if response.startswith("="):
        return response[1:].strip()
    else:
        raise ValueError(f"KataGo rejected '{command}': {response.strip()}")


# Initialise on startup
katago_process = start_katago()


class GameState(BaseModel):
    history: list[str]
    difficulty: str
    board_size: int = 19


# ---------------------------------------------------------
# WebSocket Connection Manager for Online Multiplayer
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        # Maps room_id to a list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        
        # Prevent more than 2 players from joining as active players
        if len(self.active_connections[room_id]) >= 2:
            await websocket.send_json({"type": "error", "message": "Room is full"})
            await websocket.close()
            return False

        self.active_connections[room_id].append(websocket)
        
        # First to join is Black, second is White
        color = "black" if len(self.active_connections[room_id]) == 1 else "white"
        await websocket.send_json({"type": "init", "color": color})

        # Start the game when 2 players are present
        if len(self.active_connections[room_id]) == 2:
            await self.broadcast(room_id, {"type": "start"})
            
        return True

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)

manager = ConnectionManager()


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")


@app.post("/api/move")
async def play_move(state: GameState):
    """Used for 1-Player vs AI."""
    visits_map = {"easy": 10, "medium": 100, "hard": 500}
    max_visits = visits_map.get(state.difficulty, 100)

    try:
        send_gtp_command("clear_board")
        send_gtp_command(f"boardsize {state.board_size}")
        try:
            send_gtp_command(f"kata-set-param maxVisits {max_visits}")
        except Exception:
            pass 

        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            send_gtp_command(f"play {colors[idx % 2]} {move}")

        ai_color = colors[len(state.history) % 2]
        ai_move = send_gtp_command(f"genmove {ai_color}")

        score = None
        if "RESIGN" in ai_move.upper():
            winner = "W" if ai_color == "black" else "B"
            score = f"{winner}+R"
        elif "PASS" in ai_move.upper():
            score = send_gtp_command("final_score")
            if not score or score.upper() == "PASS":
                score = send_gtp_command("kata-compute-score")

        return {"ai_move": ai_move, "score": score}

    except Exception as e:
        print(f"Backend error: {e}")
        return {"ai_move": "PASS", "score": "B+0.5"}


@app.post("/api/score")
async def calculate_score(state: GameState):
    """Used to score the board for 2-Player (Local & Online) when both pass."""
    try:
        send_gtp_command("clear_board")
        send_gtp_command(f"boardsize {state.board_size}")
        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            if move.upper() != "PASS":
                send_gtp_command(f"play {colors[idx % 2]} {move}")
        
        score = send_gtp_command("kata-compute-score")
        return {"score": score}
    except Exception as e:
        print(f"Scoring error: {e}")
        return {"score": "Unknown"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    success = await manager.connect(websocket, room_id)
    if not success:
        return
        
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            # Route the move/pass/resign to both players in the room
            await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        await manager.broadcast(room_id, {"type": "opponent_disconnected"})
