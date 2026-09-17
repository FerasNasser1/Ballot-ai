"""Start the Baloot desktop game.

    python main.py                 # default AI strength
    python main.py --samples 50    # stronger, slower AI
    python main.py --seed 7        # reproducible deals
"""

import argparse
import logging
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Play Saudi Baloot against AI agents.")
    parser.add_argument("--samples", type=int, default=30,
                        help="Monte Carlo samples per AI decision (default 30)")
    parser.add_argument("--think-time", type=float, default=1.0,
                        help="seconds the AI may search per card (default 1.0)")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducible games")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 is not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    from baloot.gui.theme import APP_QSS, ui_font
    from baloot.gui.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Baloot")
    app.setFont(ui_font(14))
    app.setStyleSheet(APP_QSS)
    window = MainWindow(samples=args.samples, time_budget=args.think_time, seed=args.seed)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
