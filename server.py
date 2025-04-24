from concurrent import futures
import grpc
import time
import threading

import memory_game_pb2 as pb
import memory_game_pb2_grpc as pb_grpc
from game_logic import Game
from shared_game import game_instance



class MemoryGameService(pb_grpc.MemoryGameServicer):
    def __init__(self):
        self.game = game_instance
        self.subscribers = []

    def JoinGame(self, request, context):
        player_id = self.game.register_player(request.name)
        print(f"Jugador conectado: {request.name} -> ID: {player_id}")
        return pb.PlayerId(id=player_id)

    def PlayTurn(self, request, context):
        print("✅ ¡Entró a PlayTurn!")
        try:
            pos1 = (request.x1, request.y1)
            pos2 = (request.x2, request.y2)
            success, message = self.game.play_turn(request.player_id, pos1, pos2)
            self.notify_all()
            print(f"[Turno] Ahora le toca al jugador: {self.game.get_current_turn_player()[:8]}")
            return pb.TurnResponse(success=success, message=message)
        except Exception as e:
            print(f"[ERROR en PlayTurn] {e}")
            return pb.TurnResponse(success=False, message="Error interno del servidor")


    def GetBoardState(self, request, context):
        return self.build_board_state()

    def SubscribeToUpdates(self, request, context):
        def event_stream():
            subscriber = threading.Event()
            self.subscribers.append(subscriber)
            while True:
                subscriber.wait()
                yield self.build_board_state()
                subscriber.clear()
        return event_stream()

    def notify_all(self):
        for s in self.subscribers:
            s.set()

    def build_board_state(self):
        cells = [
            pb.Cell(
                x=cell["x"],
                y=cell["y"],
                value=cell["value"],
                revealed=cell["revealed"],
                matched=cell["matched"]
            )
            for cell in self.game.get_public_view()
        ]
        return pb.BoardState(
            cells=cells,
            current_turn_player_id=self.game.get_current_turn_player(),
            scores=self.game.scores,
            game_over=self.game.is_game_over()
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_MemoryGameServicer_to_server(MemoryGameService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Servidor iniciado en el puerto 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    import threading
    from dashboard import app

    flask_thread = threading.Thread(target=lambda: app.run(port=8000), daemon=True)
    flask_thread.start()

    serve()
