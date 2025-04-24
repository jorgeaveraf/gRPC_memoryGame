import grpc
import threading
import memory_game_pb2 as pb
import memory_game_pb2_grpc as pb_grpc

def render_board(cells, size=4):
    board = [["🂠"] * size for _ in range(size)]
    for cell in cells:
        if cell.matched or cell.value != "🂠":
            board[cell.x][cell.y] = cell.value
    print("\nTablero:")
    for row in board:
        print(" ".join(row))

def listen_updates(stub, player_id):
    for update in stub.SubscribeToUpdates(pb.PlayerId(id=player_id)):
        render_board(update.cells)

def main():
    channel = grpc.insecure_channel("localhost:50051")
    stub = pb_grpc.MemoryGameStub(channel)

    name = input("Ingresa tu nombre: ")
    response = stub.JoinGame(pb.PlayerInfo(name=name))
    player_id = response.id
    print(f"Te uniste con ID: {player_id}")


    while True:
        input("Presiona Enter cuando sea tu turno...")
        try:
            x1, y1 = map(int, input("Carta 1 (x y): ").split())
            x2, y2 = map(int, input("Carta 2 (x y): ").split())
        except ValueError:
            print("Entrada inválida. Intenta de nuevo.")
            continue

        turn_request = pb.TurnRequest(player_id=player_id, x1=x1, y1=y1, x2=x2, y2=y2)
        response = stub.PlayTurn(turn_request, timeout=5)
        print("Respuesta:", response.message)

        # Hilo para escuchar actualizaciones del tablero
        threading.Thread(target=listen_updates, args=(stub, player_id), daemon=True).start()

if __name__ == "__main__":
    main()
