from flask import Flask, render_template_string
from game_logic import Game
from shared_game import game_instance


app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Juego de Memoria - Estado</title>
    <style>
        body { font-family: sans-serif; text-align: center; }
        table { margin: auto; border-collapse: collapse; }
        td { width: 60px; height: 60px; font-size: 2em; border: 1px solid #ccc; }
    </style>
</head>
<script>
  setTimeout(() => {
    window.location.reload();
  }, 3000); // refresca cada 3 segundos
</script>
<body>
    <h1>🎮 Juego de Memoria</h1>
    <p><strong>Turno actual:</strong> {{ current_player }}</p>
    <table>
        {% for fila in board %}
        <tr>
            {% for celda in fila %}
            <td>{{ celda }}</td>
            {% endfor %}
        </tr>
        {% endfor %}
    </table>
    <h2>🔢 Puntajes</h2>
    <ul>
        {% for pid, puntos in scores.items() %}
        <li><code>{{ pid[:8] }}</code>: {{ puntos }} parejas</li>
        {% endfor %}
    </ul>
</body>
</html>
"""

@app.route('/')
def dashboard():
    with game_instance.lock:  # usa RLock para no bloquear
        public_view = game_instance.get_public_view()
        size = game_instance.size
        board = [["🂠"] * size for _ in range(size)]
        for cell in public_view:
            board[cell["x"]][cell["y"]] = cell["value"]
        return render_template_string(
            HTML_TEMPLATE,
            board=board,
            scores=game_instance.scores,
            current_player=game_instance.get_current_turn_player()[:8]
        )

if __name__ == '__main__':
    app.run(port=8000)
