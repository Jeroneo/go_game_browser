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

katago_lock = threading.Lock()
katago_process = None


def start_katago() -> subprocess.Popen:
    print("Starting KataGo engine...")
    proc = subprocess.Popen(
        KATAGO_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    time.sleep(2) 

    if proc.poll() is not None:
        error_output = proc.stderr.read()
        print("========================================")
        print("FATAL ERROR: KataGo crashed on startup!")
        print(error_output)
        print("========================================")

    return proc


def get_katago() -> subprocess.Popen:
    global katago_process
    if katago_process is None or katago_process.poll() is not None:
        print("KataGo is not running — restarting...")
        katago_process = start_katago()
    return katago_process


def send_gtp_command(command: str) -> str:
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


katago_process = start_katago()

class GameState(BaseModel):
    history: list[str]
    difficulty: str
    board_size: int = 19

# ---------------------------------------------------------
# Stateful Connection Manager for Online Multiplayer
# ---------------------------------------------------------
class RoomData:
    def __init__(self):
        self.players: Dict[str, str] = {}  # Map player_id -> "black" or "white"
        self.history: List[dict] = []      # List of all move and chat JSON payloads
        self.connections: Dict[str, WebSocket] = {} # Map player_id -> active WebSocket

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, RoomData] = {}

    async def connect(self, websocket: WebSocket, room_id: str, player_id: str):
        await websocket.accept()
        
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomData()
            
        room = self.rooms[room_id]
        
        # Assign roles to new players
        if player_id not in room.players:
            if len(room.players) == 0:
                room.players[player_id] = "black"
            elif len(room.players) == 1:
                room.players[player_id] = "white"
            else:
                # Room already has 2 registered players, reject the 3rd person
                await websocket.send_json({"type": "error", "message": "Room is full"})
                await websocket.close()
                return False
                
        # Register the active websocket
        color = room.players[player_id]
        room.connections[player_id] = websocket
        
        opponent_present = len(room.connections) == 2

        # Send initialization state to the reconnecting/joining player
        await websocket.send_json({
            "type": "init", 
            "color": color, 
            "history": room.history,
            "opponent_present": opponent_present
        })

        # If both players are actively connected, notify everyone to unpause
        if opponent_present:
            await self.broadcast(room_id, {"type": "start"})
            
        return True

    def disconnect(self, player_id: str, room_id: str):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if player_id in room.connections:
                del room.connections[player_id]
            # Note: We intentionally do NOT delete the room or the player from room.players 
            # to allow for reconnection and state persistence.

    def save_history(self, room_id: str, message: dict):
        if room_id in self.rooms:
            self.rooms[room_id].history.append(message)

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.rooms:
            for ws in self.rooms[room_id].connections.values():
                await ws.send_json(message)

manager = ConnectionManager()

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")


@app.post("/api/move")
async def play_move(state: GameState):
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
    try:
        send_gtp_command("clear_board")
        send_gtp_command(f"boardsize {state.board_size}")
        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            if move.upper() != "PASS":
                send_gtp_command(f"play {colors[idx % 2]} {move}")

        # Try standard GTP command first, then KataGo-specific extension
        score = None
        try:
            score = send_gtp_command("final_score")
        except Exception:
            pass

        if not score or score.upper() in ("", "PASS"):
            try:
                score = send_gtp_command("kata-compute-score")
            except Exception:
                pass

        return {"score": score or "B+0"}
    except Exception as e:
        print(f"Scoring error: {e}")
        return {"score": "B+0"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str = ""):
    # Notice we now accept `player_id` from query parameters
    success = await manager.connect(websocket, room_id, player_id)
    if not success:
        return
        
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Save relevant actions to the persistent room memory
            if message.get("type") in ["move", "chat"]:
                manager.save_history(room_id, message)
                
            # Route the move/pass/resign to both players in the room
            await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        manager.disconnect(player_id, room_id)
        await manager.broadcast(room_id, {"type": "opponent_disconnected"})
