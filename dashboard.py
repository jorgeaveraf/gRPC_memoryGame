from flask import Flask, render_template_string, request, redirect, url_for, session
from shared_game import game_instance
from game_logic import Game

app = Flask(__name__)
app.secret_key = "server_secreto_123"

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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Memoria – {{ game.theme_name }} ({{ game.difficulty.title() }})</title>
  <style>
    body { font-family: sans-serif; text-align: center; }
    table { margin: auto; border-collapse: collapse; }
    td { width: 60px; height: 60px; font-size: 2em; text-align: center;
         border: 1px solid #ccc; }
    td.flipped { background: #eef; }
    #gameOverBanner {
      display: none;
      position: fixed; top: 0; left: 0; right: 0;
      background: #fffae6; color: #333;
      padding: 1em; font-size: 1.5em; z-index: 1000;
    }
  </style>
  <script>
    let polling = setInterval(fetchState, 3000);

    async function fetchState() {
      const res = await fetch('/state');
      const data = await res.json();

      // actualización de celdas
      data.cells.forEach(c => {
        const td = document.getElementById(`cell-${c.x}-${c.y}`);
        const show = c.revealed || c.matched;
        td.innerText = show ? c.value : '🂠';
        td.classList.toggle('flipped', show);
      });

      // turno actual
      document.getElementById('turno').innerText = data.current_turn_name;

      // puntajes
      const ul = document.getElementById('scores');
      ul.innerHTML = '';
      for (const [pid, pts] of Object.entries(data.scores)) {
        const li = document.createElement('li');
        li.innerHTML = `<strong>${data.player_names[pid]}</strong>: ${pts} parejas`;
        ul.appendChild(li);
      }

      // fin de juego
      if (data.game_over) {
        clearInterval(polling);
        document.getElementById('winnerName').innerText = data.winner_name;
        document.getElementById('gameOverBanner').style.display = 'block';
      }
    }
  </script>
</head>
<body>
  <div id="gameOverBanner">
    🏆 ¡Juego terminado! Ganador: <span id="winnerName"></span>
  </div>

  <h1>🎮 Memoria – {{ game.theme_name }} ({{ game.difficulty.title() }})</h1>
  <p><strong>Turno actual:</strong> <span id="turno">{{ player_names[current_id] }}</span></p>

  <table>
    {% for x in range(size) %}
      <tr>
        {% for y in range(size) %}
          {% set c = cells[x*size + y] %}
          <td id="cell-{{x}}-{{y}}"
              class="{{ 'flipped' if c.matched else '' }}">
            {{ c.value if c.matched else '🂠' }}
          </td>
        {% endfor %}
      </tr>
    {% endfor %}
  </table>

  <h2>🔢 Puntajes</h2>
  <ul id="scores">
    {% for pid, pts in scores.items() %}
      <li><strong>{{ player_names[pid] }}</strong>: {{ pts }} parejas</li>
    {% endfor %}
  </ul>
</body>
</html>
"""

# Ruta para devolver el estado en JSON (para el polling AJAX)
@app.route("/state")
def state():
    from flask import jsonify
    # obtenemos el boardstate y calculamos ganador si aplica
    cells = game_instance.get_public_view()
    current_id = game_instance.get_current_turn_player()
    scores = dict(game_instance.scores)
    players = game_instance.players
    game_over = game_instance.is_game_over()

    # Si terminó, calculamos el/los ganador(es)
    winner_name = ""
    if game_over:
        maxpts = max(scores.values(), default=0)
        winners = [pid for pid, pts in scores.items() if pts == maxpts]
        # unimos nombres (por si hay empate)
        winner_name = ", ".join(players[pid] for pid in winners)

    return jsonify({
      "cells": cells,
      "current_turn_id": current_id,
      "current_turn_name": players.get(current_id, ""),
      "scores": scores,
      "player_names": players,
      "game_over": game_over,
      "winner_name": winner_name
    })


@app.route("/select_theme", methods=["GET", "POST"])
def select_theme():
    if request.method == "POST":
        theme = request.form["theme"]
        diff  = request.form["difficulty"]
        game_instance.reset_game(theme, diff)
        # marcamos en la sesión que ya eligió tema/nivel
        session['theme_selected'] = True
        return redirect(url_for("dashboard"))
    return render_template_string(SELECT_TEMPLATE, themes=Game.THEMES.keys())

@app.route("/")
def dashboard():
    # si la sesión aún no tiene el flag, redirigimos al selector
    if not session.get('theme_selected', False):
        return redirect(url_for("select_theme"))

    with game_instance.lock:
        cells   = game_instance.get_public_view()
        size    = game_instance.size
        current = game_instance.get_current_turn_player()
        return render_template_string(
            HTML_TEMPLATE,
            game=game_instance,
            cells=cells,
            size=size,
            scores=game_instance.scores,
            player_names=game_instance.players,
            current_id=current
        )


if __name__ == "__main__":
    app.run(port=8000)
