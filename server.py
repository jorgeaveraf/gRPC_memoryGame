from concurrent import futures
import grpc
import threading
import json
import datetime
import time
import sys
import memory_game_pb2 as pb
import memory_game_pb2_grpc as pb_grpc
from shared_game import game_instance

def write_game_log():
    """Serializa a JSON el estado final de la partida (incluyendo métricas)
    y lo añade a log.txt sin sobrescribir."""
    gp = game_instance
    ts = datetime.datetime.now().isoformat()

    # 1) Construimos lista ordenada de (pid, score) descendente para calcular posición
    ranking = sorted(gp.scores.items(), key=lambda x: x[1], reverse=True)
    positions = { pid: idx+1 for idx, (pid, _) in enumerate(ranking) }

    log_entry = {
        "timestamp": ts,
        "theme": gp.theme_name,
        "difficulty": gp.difficulty,
        "final_board_size": gp.size,
        "players": []
    }

    for pid, profile in gp.profiles.items():
        m = gp.metrics.get(pid, {})
        # tiempo total desde que se unió hasta ahora
        total_time = time.time() - m.get("join_time", time.time())
        # promedio de duración de turnos
        durations = m.get("turn_durations", [])
        avg_turn = sum(durations)/len(durations) if durations else 0

        log_entry["players"].append({
            "id": pid,
            "name": profile["name"],
            "age": profile["age"],
            "gender": profile["gender"],
            "score": gp.scores.get(pid, 0),
            "turns_taken": m.get("turns", 0),
            "pairs_formed": m.get("pairs", 0),
            "total_time_seconds": round(total_time, 2),
            "avg_turn_time_seconds": round(avg_turn, 2),
            "final_position": positions.get(pid, None)
        })

    # Añadimos la entrada al log
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"[LOG] Partida registrada en log.txt @ {ts}")


class MemoryGameService(pb_grpc.MemoryGameServicer):
    def __init__(self):
        self.game = game_instance
        self.subscribers: list[tuple[str, threading.Event]] = []
        self.game.last_seen = {}

    def JoinGame(self, request, context):
        player_id = self.game.register_player(
            request.name,
            request.age,
            request.gender
            )
        print(f"Jugador conectado: {request.name} ({request.age} años, {request.gender}) -> ID: {player_id}")
        # Notificamos para que, al suscribirse, vean el tablero completo 3s
        self.notify_all()
        return pb.PlayerId(id=player_id)

    def PlayTurn(self, request, context):
        pid = request.player_id
        self.game.last_seen[pid] = time.time()
        print("✅ ¡Entró a PlayTurn!")
        try:
            pos1 = (request.x1, request.y1)
            pos2 = (request.x2, request.y2)
            # usar el campo correcto
            success, message = self.game.play_turn(request.player_id, pos1, pos2)
            self.notify_all()
            if self.game.is_game_over():
                write_game_log()
            print(f"[Turno] Ahora le toca: {self.game.get_current_turn_player()[:8]}")
            return pb.TurnResponse(success=success, message=message)
        except Exception as e:
            print(f"[ERROR en PlayTurn] {e}")
            return pb.TurnResponse(success=False, message="Error interno del servidor")


    def GetBoardState(self, request, context):
        self.game.last_seen[request.id] = time.time()
        cells = self.game.get_public_view(reveal_for=request.id)
        return self._make_boardstate(cells)

    def SubscribeToUpdates(self, request, context):
        def event_stream():
            sub_ev = threading.Event()
            # usamos request.id, no request.player_id
            pid = request.id
            self.subscribers.append((pid, sub_ev))

            # primera emisión con reveal_for
            yield self._make_boardstate(
                self.game.get_public_view(reveal_for=pid)
            )

            try:
                while True:
                    sub_ev.wait()
                    # siguiente emisiones también pasan reveal_for para ocultar tras 3s
                    yield self._make_boardstate(
                        self.game.get_public_view(reveal_for=pid)
                    )
                    self.game.new_round_flag = False
                    sub_ev.clear()
            finally:
                # cuando el cliente cierra el stream
                print(f"→ Cliente desconectado: {pid}")
                # removemos su suscripción
                self.subscribers[:] = [
                    (xpid, xev) for xpid, xev in self.subscribers if xpid != pid
                ]
                # y lo quitamos de turn_order
                with self.game.lock:
                    if pid in self.game.turn_order:
                        idx = self.game.turn_order.index(pid)
                        self.game.turn_order.remove(pid)
                        if idx < self.game.current_turn:
                            self.game.current_turn -= 1
                        if self.game.turn_order:
                            self.game.current_turn %= len(self.game.turn_order)
                        else:
                            self.game.current_turn = 0

        return event_stream()


    def _make_boardstate(self, cells):
        pb_cells = []
        nr = self.game.new_round_flag
        for c in cells:
           x, y = c["x"], c["y"]
           actual = self.game.board[x][y]
           pb_cells.append(pb.Cell(
               x=x, y=y,
               value=actual,
               revealed=c["revealed"],
               matched=c["matched"]
           ))
           state = pb.BoardState(
            cells=pb_cells,
            current_turn_player_id=self.game.get_current_turn_player(),
            scores=self.game.scores,
            player_names=self.game.players,
            game_over=self.game.is_game_over(),
            new_round=nr,
            theme_name=self.game.theme_name,
            difficulty=self.game.difficulty
         )
         # resetear para la próxima emisión
        self.game.new_round_flag = False
        return state

    def notify_all(self):
        for pid, ev in self.subscribers:
            ev.set()

def start_inactivity_monitor(service, timeout=30, check_interval=10):
    def monitor():
        while True:
            time.sleep(check_interval)
            now = time.time()
            with service.game.lock:
                for pid, last in list(service.game.last_seen.items()):
                    if now - last > timeout:
                        print(f"⏱ Jugador inactivo: {pid}, removiendo de turnos")
                        # misma lógica que en el finally de SubscribeToUpdates:
                        if pid in service.game.turn_order:
                            idx = service.game.turn_order.index(pid)
                            service.game.turn_order.remove(pid)
                            if idx < service.game.current_turn:
                                service.game.current_turn -= 1
                            if service.game.turn_order:
                                service.game.current_turn %= len(service.game.turn_order)
                            else:
                                service.game.current_turn = 0
                        del service.game.last_seen[pid]
                        service.notify_all()
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()

def serve():
    # 1) Instancia el servicio
    service = MemoryGameService()

    # 2) Arranca el hilo que vigila inactividad
    start_inactivity_monitor(service, timeout=50, check_interval=10)

    # 3) Monta el servidor gRPC con esa instancia
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_MemoryGameServicer_to_server(service, server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Servidor iniciado en el puerto 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    # Lanzamos el dashboard en un hilo separado
    from dashboard import app
    flask_thread = threading.Thread(target=lambda: app.run(port=8000), daemon=True)
    flask_thread.start()

    try:
        serve()
    except KeyboardInterrupt:
        print("Servidor detenido manualmente; registrando log de la última partida…")
        write_game_log()
        sys.exit(0)
