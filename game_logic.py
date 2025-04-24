import random
import threading
import uuid

EMOJIS = ["🍓", "🍇", "🐶", "🍎", "🍌", "🐱", "🍉", "🦊"] * 2

class Game:
    def __init__(self, size=4):
        self.size = size
        self.board = []
        self.revealed = {}
        self.matched = set()
        self.players = {}
        self.turn_order = []
        self.current_turn = 0
        self.scores = {}
        self.lock = threading.RLock()
        self._initialize_board()

    def _initialize_board(self):
        total_cards = self.size * self.size
        deck = EMOJIS[:total_cards // 2] * 2
        random.shuffle(deck)
        self.board = [deck[i:i + self.size] for i in range(0, total_cards, self.size)]
        print("→ Tablero actual:")
        for row in self.board:
            print(row)


    def register_player(self, name):
        player_id = str(uuid.uuid4())
        with self.lock:
            self.players[player_id] = name
            self.turn_order.append(player_id)
            self.scores[player_id] = 0
        return player_id

    def is_players_turn(self, player_id):
        with self.lock:
            return self.turn_order[self.current_turn] == player_id

    def play_turn(self, player_id, pos1, pos2):
        x1, y1 = pos1
        x2, y2 = pos2
        with self.lock:
            if not self.is_players_turn(player_id):
                return False, "No es tu turno."
            if (x1, y1) == (x2, y2):
                print(f"Jugador {player_id} intentó jugar: {pos1} y {pos2}")
                return False, "Debes elegir dos cartas diferentes."
            try:
                card1 = self.board[x1][y1]
                card2 = self.board[x2][y2]
            except IndexError:
                return False, "Posiciones inválidas."

            is_match = card1 == card2
            if is_match:
                self.matched.update({(x1, y1), (x2, y2)})
                self.scores[player_id] += 1
            else:
                self.current_turn = (self.current_turn + 1) % len(self.turn_order)

            print(f"Cartas: {self.board[x1][y1]} y {self.board[x2][y2]}")
            return is_match, "¡Emparejaste!" if is_match else "No fue pareja."
        
        print(f"Turno actual: {self.turn_order[self.current_turn]}")


    def get_public_view(self):
        view = []
        for x in range(self.size):
            for y in range(self.size):
                cell = {
                    "x": x,
                    "y": y,
                    "value": self.board[x][y] if (x, y) in self.matched else "🂠",
                    "revealed": False,
                    "matched": (x, y) in self.matched
                }
                view.append(cell)
        return view

    def get_current_turn_player(self):
        with self.lock:
            if not self.turn_order:
                return "N/A"
            return self.turn_order[self.current_turn]


    def is_game_over(self):
        total_cards = self.size * self.size
        return len(self.matched) == total_cards