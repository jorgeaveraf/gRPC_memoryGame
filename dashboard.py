from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from shared_game import game_instance
from game_logic import Game
import time

app = Flask(__name__)
app.secret_key = "server_secreto_123"
app.config['SESSION_COOKIE_NAME'] = 'dashboard_session'

SELECT_TEMPLATE = """
<!DOCTYPE html>
<html><body>
  <h1>Selecciona Tema y Nivel</h1>
  <form method="post">
    <fieldset>
      <legend>Tema</legend>
      {% for key in themes %}
        <label>
          <input type="radio" name="theme" value="{{key}}" required>
          {{ key.title() }}
        </label><br>
      {% endfor %}
    </fieldset>
    <fieldset>
      <legend>Nivel</legend>
      <label><input type="radio" name="difficulty" value="easy" checked>Fácil</label><br>
      <label><input type="radio" name="difficulty" value="hard">Difícil</label><br>
    </fieldset>
    <button>Iniciar Partida</button>
  </form>
</body></html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Memoria – {{ game.theme_name|title }} ({{ game.difficulty|title }})</title>
  <style>
    body { font-family: sans-serif; text-align: center; }
    table { margin: auto; border-collapse: collapse; }
    td, th { border: 1px solid #ccc; padding: 8px; }
    td { width: 60px; height: 60px; font-size: 2em; text-align: center; }
    th { background: #f0f0f0; }
    #gameOverBanner {
      display: none; position: fixed; top:0; left:0; right:0;
      background: #fffae6; color:#333; padding:1em; font-size:1.5em; z-index:1000;
    }
    #options { margin: 1em; }
    #options form { display: inline-block; margin: 0 0.5em; }
  </style>
  <script>
    let polling = setInterval(fetchState, 3000);
    async function fetchState() {
      const res = await fetch('/state');
      const data = await res.json();
      // 1) tablero
      data.cells.forEach(c=>{
        const td = document.getElementById(`cell-${c.x}-${c.y}`);
        const show = c.revealed||c.matched;
        td.innerText = show?c.value:'🂠';
        td.classList.toggle('flipped', show);
      });
      // 2) turno
      document.getElementById('turno').innerText = data.current_turn_name;
      // 3) puntajes
      const ul = document.getElementById('scores');
      ul.innerHTML = '';
      for(const [pid,pts] of Object.entries(data.scores)){
        const li = document.createElement('li');
        li.innerHTML = `<strong>${data.player_names[pid]}</strong>: ${pts} parejas`;
        ul.appendChild(li);
      }
      // 4) métricas y banner + mostrar opciones
      if(data.game_over){
        clearInterval(polling);
        document.getElementById('winnerName').innerText = data.winner_name;
        document.getElementById('gameOverBanner').style.display = 'block';
        // métricas
        const mt = document.getElementById('metrics-body');
        mt.innerHTML = '';
        data.metrics.forEach(m=>{
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${m.name}</td>
            <td>${m.score}</td>
            <td>${m.turns}</td>
            <td>${m.pairs}</td>
            <td>${m.total_time}</td>
            <td>${m.avg_turn_time}</td>`;
          mt.appendChild(row);
        });
        // mostramos las acciones
        document.getElementById('options').style.display = 'block';
      }
    }
  </script>
</head>
<body>
  <div id="gameOverBanner">
    🏆 ¡Juego terminado! Ganador: <span id="winnerName"></span>
  </div>

  <h1>🎮 Memoria – {{ game.theme_name|title }} ({{ game.difficulty|title }})</h1>
  <p><strong>Turno actual:</strong> <span id="turno">{{ player_names[current_id] }}</span></p>

  <table>
    {% for x in range(size) %}
      <tr>
      {% for y in range(size) %}
        {% set c = cells[x*size+y] %}
        <td id="cell-{{x}}-{{y}}" class="{{ 'flipped' if c.matched else '' }}">
          {{ c.value if c.matched else '🂠' }}
        </td>
      {% endfor %}
      </tr>
    {% endfor %}
  </table>

  <h2>🔢 Puntajes</h2>
  <ul id="scores">
    {% for pid,pts in scores.items() %}
      <li><strong>{{ player_names[pid] }}</strong>: {{ pts }} parejas</li>
    {% endfor %}
  </ul>

  <h2>📊 Métricas de Jugadores</h2>
  <table>
    <thead>
      <tr>
        <th>Jugador</th><th>Puntaje</th><th>Turnos</th>
        <th>Pares</th><th>Tiempo (s)</th><th>Promedio Turno (s)</th>
      </tr>
    </thead>
    <tbody id="metrics-body"></tbody>
  </table>

  <!-- Opciones tras game over -->
  <div id="options" style="display:none;">
    <form method="post" action="{{ url_for('restart') }}">
      <button>Reiniciar</button>
    </form>
    <form method="post" action="{{ url_for('reconfigure') }}">
      <button>Reconfigurar</button>
    </form>
    <form method="post" action="{{ url_for('shutdown') }}">
      <button>Cerrar</button>
    </form>
  </div>
</body>
</html>
"""

@app.route("/state")
def state():
    # 1) Estado básico
    cells      = game_instance.get_public_view()
    current_id = game_instance.get_current_turn_player()
    scores     = dict(game_instance.scores)
    players    = game_instance.players
    game_over  = game_instance.is_game_over()
    new_round   = getattr(game_instance, "new_round_flag", False)
    theme_name  = game_instance.theme_name
    difficulty  = game_instance.difficulty

    # 2) Inicializo métricas y ganador
    metrics     = []
    winner_name = ""

    if game_over:
        # — Ordeno jugadores por puntaje descendente
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

        # — Determino ganador/es (en caso de empate)
        maxpts   = ranked[0][1] if ranked else 0
        winners  = [pid for pid, pts in ranked if pts == maxpts]
        winner_name = ", ".join(players[pid] for pid in winners)

        # — Armo la tabla de métricas
        for pid, _ in ranked:
            m = game_instance.metrics.get(pid, {})
            join_time = m.get("join_time", time.time())
            total_time = round(time.time() - join_time, 2)

            durations = m.get("turn_durations", [])
            avg_turn = round(sum(durations) / len(durations), 2) if durations else 0.0

            metrics.append({
                "name":         players[pid],
                "score":        scores[pid],
                "turns":        m.get("turns", 0),
                "pairs":        m.get("pairs", 0),
                "total_time":   total_time,
                "avg_turn_time": avg_turn
            })

    # 3) Devuelvo todo en JSON
    print(f"[STATE] new_round={new_round}, theme={theme_name}, diff={difficulty}")
    print("[STATE] JSON keys =", ['cells','current_turn_id','game_over',
                                  'new_round','theme_name','difficulty'])


    return jsonify({
        "cells":             cells,
        "current_turn_id":   current_id,
        "current_turn_name": players.get(current_id, ""),
        "scores":            scores,
        "player_names":      players,
        "game_over":         game_over,
        "winner_name":       winner_name,
        "metrics":           metrics,
        "new_round":         new_round,
        "theme_name":        theme_name,
        "difficulty":        difficulty
    })

@app.route("/select_theme", methods=["GET","POST"])
def select_theme():
    if request.method == "POST":
        theme = request.form["theme"]
        diff  = request.form["difficulty"]

        if not game_instance.players:
            game_instance.reset_game(theme, diff)
        else:
            # Ya había jugadores: reconfiguro sólo el tablero, sin borrar jugadores
            game_instance.new_round(theme, diff)

        session["theme_selected"] = True
        return redirect(url_for("dashboard"))
    return render_template_string(SELECT_TEMPLATE,
                                  themes=Game.THEMES.keys())

@app.route("/")
def dashboard():
    if (not session.get("theme_selected")) or (game_instance.theme_name is None):
        session.pop("theme_selected", None)
        return redirect(url_for("select_theme"))

    with game_instance.lock:
        cells      = game_instance.get_public_view()
        size       = game_instance.size
        current_id = game_instance.get_current_turn_player()
        return render_template_string(
            DASHBOARD_TEMPLATE,
            game=game_instance,
            cells=cells,
            size=size,
            scores=game_instance.scores,
            player_names=game_instance.players,
            current_id=current_id
        )

@app.route("/restart", methods=["POST"])
def restart():
    game_instance.new_round()
    session["theme_selected"] = True
    return redirect(url_for("dashboard"))

@app.route("/reconfigure", methods=["POST"])
def reconfigure():
    game_instance.new_round_flag = True
    session.pop("theme_selected", None)
    return redirect(url_for("select_theme"))

@app.route("/shutdown", methods=["POST"])
def shutdown():
    # apaga el servidor Flask
    func = request.environ.get("werkzeug.server.shutdown")
    if func:
        func()
    return "Servidor cerrado", 200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=8000)
