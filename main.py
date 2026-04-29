import sys
import traceback
from pathlib import Path

APP_ICON_PATH = Path(__file__).resolve().parent / "resources" / "app_icon.ico"


def run_office_bridge_if_requested() -> None:
    if "--office-bridge" not in sys.argv:
        return
    sys.argv.remove("--office-bridge")
    from core.office_bridge import main as office_bridge_main

    raise SystemExit(office_bridge_main())


def run():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    try:
        run_office_bridge_if_requested()
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
