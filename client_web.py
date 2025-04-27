from flask import Flask, jsonify, render_template, request, redirect, session, url_for
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
        name   = request.form["name"]
        age    = int(request.form["age"])
        gender = request.form["gender"]
        resp = stub.JoinGame(pb.PlayerInfo(name=name, age=age, gender=gender))
        # guardamos todo en sesión
        session["player_id"]     = resp.id
        session["player_name"]   = name
        session["player_age"]    = age
        session["player_gender"] = gender
        return redirect(url_for("jugar"))
    # GET
    return render_template("index.html")

@app.route("/jugar", methods=["GET"])
def jugar():
    player_id = session.get("player_id")
    if not player_id:
        return redirect(url_for("index"))
    
    board_state = stub.GetBoardState(pb.PlayerId(id=player_id))

    cells = board_state.cells
    size = int(len(cells) ** 0.5)

    reveal_active = any(c.revealed and not c.matched for c in board_state.cells)
    return render_template("tablero.html",
                           cells=cells,
                           size=size,
                           turno_id=board_state.current_turn_player_id,
                           player_name=session["player_name"],
                           player_names=board_state.player_names,
                           puntos=board_state.scores,
                           reveal_active=reveal_active,
                           enumerate=enumerate
                           )    

@app.route("/jugar", methods=["POST"])
def jugar_post():
    player_id = session["player_id"]
    x1, y1 = int(request.form["x1"]), int(request.form["y1"])
    x2, y2 = int(request.form["x2"]), int(request.form["y2"])
    turn_req = pb.TurnRequest(player_id=player_id, x1=x1, y1=y1, x2=x2, y2=y2)
    stub.PlayTurn(turn_req)
    return redirect(url_for("jugar"))


@app.route("/state")
def state():
    # 1. Obtengo ID del cliente desde sesión o parámetro
    pid = session["player_id"]

    # 2. Invoco el RPC que me devuelve el estado completo
    resp = stub.GetBoardState(pb.PlayerId(id=pid))

    # 3. Serializo las celdas en lista de dicts
    cells = [
        {"x": c.x, "y": c.y, "value": c.value,
         "revealed": c.revealed, "matched": c.matched}
        for c in resp.cells
    ]

    # 4. Convierto scores y nombres a dicts de Python
    scores = dict(resp.scores)
    names  = dict(resp.player_names)
    game_over = resp.game_over
    current_id = resp.current_turn_player_id

    # 5. Si terminó, calculo ganador/es
    winner_name = ""
    if game_over:
        max_pts = max(scores.values(), default=0)
        winners = [pid for pid, pts in scores.items() if pts == max_pts]
        # por si hay empate, uno o varios nombres separados por coma
        winner_name = ", ".join(names[pid] for pid in winners)

    # 6. Devuelvo JSON limpio
    return jsonify({
        "cells": cells,
        "current_turn_id": current_id,
        "current_turn_name": names.get(current_id, ""),
        "scores": scores,
        "player_names": names,
        "game_over": game_over,
        "winner_name": winner_name
    })


if __name__ == "__main__":
    app.run(port=8081, debug=True)
