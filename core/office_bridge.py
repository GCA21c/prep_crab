from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path


def _result(ok: bool, error: str = '') -> int:
    print(json.dumps({'ok': ok, 'error': error}, ensure_ascii=False), flush=True)
    return 0 if ok else 1


def convert_word(src: Path, out_pdf: Path) -> int:
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except Exception as exc:
        return _result(False, f'pywin32 import 실패: {exc}')

    word = None
    doc = None
    try:
        pythoncom.CoInitialize()
        try:
            word = win32com.client.DispatchEx('Word.Application')
        except Exception:
            word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(
            FileName=str(src),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Revert=False,
            NoEncodingDialog=True,
            OpenAndRepair=True,
        )
        try:
            doc.ExportAsFixedFormat(
                OutputFileName=str(out_pdf),
                ExportFormat=17,
                OpenAfterExport=False,
                OptimizeFor=0,
                Range=0,
                Item=0,
                CreateBookmarks=1,
            )
        except Exception:
            doc.SaveAs(str(out_pdf), FileFormat=17)
        if out_pdf.exists() and out_pdf.stat().st_size > 0:
            return _result(True)
        return _result(False, 'Word가 PDF 파일을 생성하지 않았습니다.')
    except Exception as exc:
        return _result(False, str(exc))
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _set_hwp_visibility(hwp, visible: bool) -> None:
    try:
        hwp.XHwpWindows.Item(0).Visible = visible
        return
    except Exception:
        pass
    try:
        hwp.Visible = visible
    except Exception:
        pass


def _bring_hwp_to_front(hwp) -> None:
    try:
        hwp.XHwpWindows.Item(0).Visible = True
    except Exception:
        pass
    try:
        hwp.XHwpWindows.Item(0).Activate()
    except Exception:
        pass
    try:
        hwnd = int(hwp.XHwpWindows.Item(0).Handle)
    except Exception:
        hwnd = 0
    if hwnd:
        try:
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 5)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
    time.sleep(0.2)


def _hwp_open(hwp, src: Path) -> tuple[bool, str]:
    attempts = (
        lambda: hwp.Open(str(src), '', 'forceopen:true'),
        lambda: hwp.Open(str(src), 'HWP', 'forceopen:true'),
        lambda: hwp.Open(str(src)),
    )
    last_error = ''
    for attempt in attempts:
        try:
            _bring_hwp_to_front(hwp)
            result = attempt()
            if result is None or bool(result):
                return True, ''
        except Exception as exc:
            last_error = str(exc)
    return False, last_error or '한글이 문서를 열지 못했습니다.'


def _hwp_save_pdf(hwp, out_pdf: Path) -> tuple[bool, str]:
    attempts = (
        lambda: hwp.SaveAs(str(out_pdf), 'PDF'),
        lambda: hwp.SaveAs(str(out_pdf), 'PDF', ''),
        lambda: hwp.SaveAs(str(out_pdf), 'PDF', 'export'),
    )
    last_error = ''
    for attempt in attempts:
        try:
            result = attempt()
            if (result is None or bool(result)) and out_pdf.exists() and out_pdf.stat().st_size > 0:
                return True, ''
        except Exception as exc:
            last_error = str(exc)
    return False, last_error or '한글이 PDF 파일을 생성하지 않았습니다.'


def convert_hwp(src: Path, out_pdf: Path) -> int:
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except Exception as exc:
        return _result(False, f'pywin32 import 실패: {exc}')

    hwp = None
    try:
        pythoncom.CoInitialize()
        try:
            hwp = win32com.client.DispatchEx('HWPFrame.HwpObject')
        except Exception:
            hwp = win32com.client.Dispatch('HWPFrame.HwpObject')
        # HWP/HWPX often triggers Hancom's access-permission dialog. Keep the
        # window visible and foreground so the user can approve it.
        _set_hwp_visibility(hwp, True)
        _bring_hwp_to_front(hwp)
        ok, error = _hwp_open(hwp, src)
        if not ok:
            return _result(False, error)
        ok, error = _hwp_save_pdf(hwp, out_pdf)
        if not ok:
            return _result(False, error)
        return _result(True)
    except Exception as exc:
        return _result(False, str(exc))
    finally:
        try:
            if hwp is not None:
                hwp.Clear(1)
        except Exception:
            pass
        try:
            if hwp is not None:
                hwp.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('word', 'hwp'), required=True)
    parser.add_argument('--src', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    src = Path(args.src).expanduser().resolve()
    out_pdf = Path(args.out).expanduser().resolve()
    try:
        if out_pdf.exists():
            out_pdf.unlink()
    except Exception:
        pass
    if args.kind == 'word':
        return convert_word(src, out_pdf)
    return convert_hwp(src, out_pdf)


if __name__ == '__main__':
    sys.exit(main())
