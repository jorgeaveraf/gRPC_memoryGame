import random
import threading
import uuid
import time

class Game:
    # Temáticas disponibles
    THEMES = {
        "emojis":    ["🍓","🍇","🐶","🍎","🍌","🐱","🍉","🦊"],
        "animals":   ["🐶","🐱","🦊","🐻","🐼","🐸","🐵","🐯"],
        "countries": ["🇺🇸","🇫🇷","🇯🇵","🇧🇷","🇩🇪","🇮🇳","🇨🇦","🇲🇽"],
        "shapes":    ["■","▲","●","★","✿","♦","♥","♣"]
    }

    def __init__(self, size=4):
        # Tamaño base para nivel fácil
        self.initial_size = size
        self.lock = threading.RLock()

        # Estado del juego (se inicializa en reset_game)
        self.theme_name     = None
        self.difficulty     = None
        self.size           = None
        self.board          = []

        # Jugadores y perfiles
        self.players        = {}  # pid → name
        self.profiles       = {}  # pid → { name, age, gender }

        # Métricas NEW
        self.metrics        = {}  # pid → { turns, turn_durations, pairs, join_time }
        self.turn_start     = {}  # pid → timestamp cuando empezó su turno

        # Tiempos de unión y orden de turnos
        self.join_times     = {}  # pid → timestamp de register_player
        self.turn_order     = []  # lista de pids
        self.current_turn   = 0

        # Puntuaciones y cartas emparejadas
        self.scores         = {}  # pid → parejas conseguidas
        self.matched        = set()

    def reset_game(self, theme_name, difficulty):
        """Reinicia todo: tablero, jugadores, métricas, etc."""
        with self.lock:
            # Limpia métricas y temporales
            self.metrics.clear()
            self.turn_start.clear()
            self.players.clear()
            self.profiles.clear()
            self.join_times.clear()
            self.turn_order.clear()
            self.current_turn = 0
            self.scores.clear()
            self.matched.clear()

            # Selección de tema y tamaño
            self.theme_name = theme_name
            self.difficulty = difficulty
            if difficulty == "easy":
                self.size = self.initial_size
                base = Game.THEMES.get(theme_name, Game.THEMES["emojis"])
            else:
                # hard: tamaño doble, ficha mezclada
                self.size = self.initial_size * 2
                base = []
                for lst in Game.THEMES.values():
                    base.extend(lst)

            # Construcción del mazo con pares
            total_cards = self.size * self.size
            total_pairs = total_cards // 2
            # Repetir cada símbolo el número de pares necesario
            deck = []
            icons = base[:total_pairs] if difficulty=="easy" else base
            for icon in icons:
                deck.extend([icon, icon])
            # Si faltan cartas (redondeo), rellenar con más pares
            idx = 0
            while len(deck) < total_cards:
                icon = base[idx % len(base)]
                deck.extend([icon, icon])
                idx += 1

            random.shuffle(deck)
            # Matriz
            self.board = [deck[i:i+self.size]
                          for i in range(0, total_cards, self.size)]

            print(f"→ Nuevo juego: tema={self.theme_name}, nivel={self.difficulty}, size={self.size}×{self.size}")

    def register_player(self, name, age, gender):
        """Registra un jugador y arranca su métrica/turno."""
        pid = str(uuid.uuid4())
        now = time.time()
        with self.lock:
            self.players[pid]  = name
            self.profiles[pid] = {"name": name, "age": age, "gender": gender}

            # Inicializamos métricas NEW
            self.metrics[pid] = {
                "turns": 0,
                "turn_durations": [],
                "pairs": 0,
                "join_time": now
            }

            self.join_times[pid]   = now
            self.turn_order.append(pid)
            self.scores[pid]       = 0

            # Si es el primer jugador o turno vacío, arrancamos su contador
            if len(self.turn_order) == 1:
                self.turn_start[pid] = now

        return pid

    def is_players_turn(self, pid):
        with self.lock:
            return bool(self.turn_order) and self.turn_order[self.current_turn] == pid

    def play_turn(self, pid, pos1, pos2):
        """Ejecuta la jugada, actualiza métricas y controla cambio de turno."""
        now = time.time()
        x1,y1 = pos1
        x2,y2 = pos2

        with self.lock:
            # 1) tiempo de turno anterior
            if pid in self.turn_start:
                duration = now - self.turn_start[pid]
                self.metrics[pid]["turn_durations"].append(duration)

            # 2) conteo de turnos
            self.metrics[pid]["turns"] += 1

            # Validaciones
            if not self.is_players_turn(pid):
                return False, "No es tu turno."
            if (x1,y1) == (x2,y2):
                return False, "Debes elegir dos cartas diferentes."
            if not (0<=x1<self.size and 0<=y1<self.size and
                    0<=x2<self.size and 0<=y2<self.size):
                return False, "Posición fuera de rango."

            # Comparar
            c1 = self.board[x1][y1]
            c2 = self.board[x2][y2]
            match = (c1 == c2)
            if match:
                self.matched.update({(x1,y1),(x2,y2)})
                self.scores[pid] += 1
                self.metrics[pid]["pairs"] += 1
                # se queda en su turno
            else:
                # cambiar turno solo si hay más de un jugador
                if len(self.turn_order) > 1:
                    self.current_turn = (self.current_turn + 1) % len(self.turn_order)

            # 3) arrancar el timer del siguiente jugador
            next_pid = self.turn_order[self.current_turn]
            self.turn_start[next_pid] = now

            return match, "¡Emparejaste!" if match else "No fue pareja."

    def get_public_view(self, reveal_for=None):
        """Devuelve lista de celdas con estado (x,y,value,revealed,matched)."""
        now = time.time()
        show_all = False
        if reveal_for and (now - self.join_times.get(reveal_for, 0) < 3):
            show_all = True

        view = []
        for x in range(self.size):
            for y in range(self.size):
                is_matched = (x,y) in self.matched
                revealed   = show_all or is_matched
                val        = self.board[x][y] if revealed else "🂠"
                view.append({
                    "x": x, "y": y,
                    "value": val,
                    "revealed": revealed,
                    "matched": is_matched
                })
        return view

    def get_current_turn_player(self):
        with self.lock:
            return self.turn_order[self.current_turn] if self.turn_order else None

    def is_game_over(self):
        return len(self.matched) == self.size * self.size
