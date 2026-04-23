import os
import sys
import traceback

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)


def run():
    from PySide6.QtWidgets import QApplication
    from doc_capture_proto.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    print("[INFO] main.py start")
    try:
        code = run()
        print(f"[INFO] app exit code = {code}")
    except Exception:
        print("\n[FATAL ERROR]")
        traceback.print_exc()
    finally:
        input("\n엔터 누르기 전까지 안 닫힘 > ")
