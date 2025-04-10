from automated_lle.implementations.SDL7.deck_sdl7 import DeckSDL7
import ivoryos

deck = DeckSDL7()


if __name__ == "__main__":
    ivoryos.run(__name__)