from flask import Flask, render_template, request, redirect, session, url_for
import grpc
import memory_game_pb2 as pb
import memory_game_pb2_grpc as pb_grpc

app = Flask(__name__)
app.secret_key = "jugador_secreto_123"

# Conexión gRPC al servidor
channel = grpc.insecure_channel("localhost:50051")
stub = pb_grpc.MemoryGameStub(channel)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"]
        response = stub.JoinGame(pb.PlayerInfo(name=name))
        session["player_id"] = response.id
        return redirect(url_for("jugar"))
    return '''
    <h1>🎮 Unirse al juego</h1>
    <form method="post">
        Nombre: <input name="name" />
        <input type="submit" value="Entrar" />
    </form>
    '''

@app.route("/jugar", methods=["GET"])
def jugar():
    player_id = session.get("player_id")
    if not player_id:
        return redirect(url_for("index"))
    board_state = stub.GetBoardState(pb.PlayerId(id=player_id))
    size = 4
    board = [["🂠"] * size for _ in range(size)]
    for cell in board_state.cells:
        board[cell.x][cell.y] = cell.value if cell.revealed or cell.matched else "🂠"
    return render_template("tablero.html", board=board, turno=board_state.current_turn_player_id[:8], puntos=board_state.scores, enumerate=enumerate)

@app.route("/jugar", methods=["POST"])
def jugar_post():
    player_id = session["player_id"]
    x1, y1 = int(request.form["x1"]), int(request.form["y1"])
    x2, y2 = int(request.form["x2"]), int(request.form["y2"])
    turn_req = pb.TurnRequest(player_id=player_id, x1=x1, y1=y1, x2=x2, y2=y2)
    stub.PlayTurn(turn_req)
    return redirect(url_for("jugar"))

if __name__ == "__main__":
    app.run(port=8081, debug=True)
