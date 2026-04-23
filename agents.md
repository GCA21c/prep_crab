# agents.md

## 프로젝트 개요

이 프로젝트는 **문서 캡쳐 - 이식 - PDF 생성 GUI 프로그램**이다.  
주요 목표는 다음과 같다.

- ORIGIN에서 원본 문서를 페이지 단위로 열람
- 줌/팬 상태에서 캡쳐 박스로 영역 지정
- 지정 영역을 **자동 영역 추적(trim + margin)** 하여 CLIPBOARD에 저장
- CLIPBOARD 항목을 HERE 페이지에 배치
- HERE에서 레이아웃 편집 후 PDF 출력
- 최종적으로 PDF, DOCX, HWP/HWPX까지 가능한 범위에서 읽기 전용으로 다룬다

이 문서는 **Codex가 현재 상태를 빠르게 파악하고, 기능을 망가뜨리지 않고 후속 개발**하기 위한 작업 지침서다.

---

## 현재 소스 구조

현재 기준 핵심 파일:

- `main.py`  
  루트 실행 래퍼. `python main.py` 실행 가능해야 한다.
- `run_main.bat`  
  Windows 실행용 배치 파일. 항상 유지할 것.
- `doc_capture_proto/main.py`  
  패키지 엔트리.
- `doc_capture_proto/ui/main_window.py`  
  전체 윈도우 조립, 패널 연결, undo, load/save, 신호 연결.
- `doc_capture_proto/ui/origin_view.py`  
  ORIGIN 렌더링, 캡쳐박스, 줌/팬, live preview, capture.
- `doc_capture_proto/ui/clipboard_view.py`  
  CLIPBOARD 리스트 / 미리보기 / drag source / help 영역.
- `doc_capture_proto/ui/here_view.py`  
  HERE 페이지, 블럭 배치, 선택, 드래그, 리사이즈, magnet, 복붙.
- `doc_capture_proto/core/document_loader.py`  
  PDF/DOC/DOCX/HWP/HWPX 로더 분기.
- `doc_capture_proto/core/capture_utils.py`  
  영역 추적(trim) 관련 유틸.
- `doc_capture_proto/core/clipboard_store.py`  
  clipboard item 저장소.
- `doc_capture_proto/core/project_store.py`  
  프로젝트 저장/불러오기.
- `doc_capture_proto/core/pdf_exporter.py`  
  HERE 페이지를 PDF로 출력.

---

## 현재 기능 상태 요약

### ORIGIN
구현됨:
- PDF 문서 열기
- 다중 문서 로드
- 문서별 페이지 이동
- 마우스 커서 중심 줌
- space / middle mouse 기반 grab-pan
- live preview
- capture box 이동/리사이즈
- capture 버튼 / 박스 더블클릭 캡쳐
- auto trim 기반 영역 추적

문제/주의:
- 팬/줌/문서 전환 관련 상태가 쉽게 꼬일 수 있으므로 좌표계 수정 시 매우 조심
- live preview 성능 저하 가능성 있음
- multi-document UI 슬롯은 시각적으로만 맞춘 상태일 수 있으므로 기능 추가 전 구조 점검 필요

### CLIPBOARD
구현됨:
- 캡쳐 리스트업
- live preview 표시
- 리스트 스크롤
- drag source
- help 패널

문제/주의:
- HERE와 selection sync는 필요하지만 **포커스를 CLIPBOARD에 넘기면 안 됨**
- 이전에 HERE 선택 시 CLIPBOARD 활성화되어 HERE 단축키가 먹지 않는 버그가 있었음

### HERE
구현됨:
- 다중 페이지
- 캡쳐 블럭 온보드
- 선택/드래그/리사이즈
- 페이지별 줌/팬 상태 일부 유지
- copy / paste
- delete
- shadow / selection UI 일부
- magnet / guide line 일부

문제/주의:
- 방향키 이동이 반복적으로 불안정했음
- selection focus가 CLIPBOARD로 넘어가면 HERE 입력이 깨짐
- magnet은 여러 번 퇴행했음. 특히 “상하 스냅이 섞여 동작이 어색해지는 문제”가 자주 발생
- 현재 목표 magnet은 **위/아래 블럭의 좌/우 정렬 전용**
  - 예시:
    - 위 블럭의 좌측 기준선
    - 아래 블럭의 좌측 기준선
    - 또는 우측 기준선
  - 상하끼리 들러붙는 스냅은 제거해야 함

### DOC/DOCX
현재 로더 구조:
- DOCX:
  - Word COM -> PDF bridge 우선
  - `mammoth`
  - `python-docx`
  - zip/xml fallback
- DOC:
  - Word COM text/PDF bridge
  - `textract`
  - `olefile` 기반 텍스트 후보 추출

현실 판단:
- DOCX는 반드시 어느 정도 읽혀야 한다. “백지”가 나오면 버그로 간주.
- DOC는 환경 의존성이 크지만, 최소한 텍스트 읽기 전용 preview는 되어야 한다.

### HWP/HWPX
현재 로더 구조:
- `simple-hwp2pdf`
- `pyhwpx`
- 기타 텍스트 fallback

현실 판단:
- HWP/HWPX는 현재 미완성 상태
- 외부 한글 설치 없는 환경에서 “PDF처럼 완전 렌더”는 어렵다
- 그러나 HWP 5.x 바이너리 샘플을 보면 텍스트/표/문단 구조 파싱은 가능성이 높다
- 장기적으로는 **자체 HWP loader + page renderer**로 가는 게 맞다

---

## 절대 잊지 말아야 할 과거 버그

### 1. eventFilter 오용
과거에 아래 같은 코드로 프로그램이 즉시 죽었다.

```python
if event.type() == event.KeyPress:
```

정상은 반드시:
```python
from PySide6.QtCore import QEvent
if event.type() == QEvent.KeyPress:
```

### 2. HERE 선택 -> CLIPBOARD 활성화
증상:
- HERE 블럭 선택 시 CLIPBOARD 불이 들어오고
- 방향키 / 삭제 / 실시간 편집이 HERE가 아니라 CLIPBOARD로 먹음

원인:
- selection sync와 focus transfer를 혼동했기 때문

원칙:
- HERE 선택 시 CLIPBOARD 리스트 선택 표시만 갱신
- **focus / active panel은 HERE 유지**

### 3. ContentBounds를 method처럼 호출
과거 예외:
- `bounds.left()` / `bounds.right()`  
실제는 속성형일 수 있음:
- `bounds.left`, `bounds.right`

반환 타입 확인 없이 메서드 호출하지 말 것.

### 4. magnet 로직 중복 정의
과거에 `_apply_magnet()`가 중복으로 정의되어 뒤쪽 구현이 앞쪽 구현을 덮어써 기능이 퇴행했다.

원칙:
- magnet 로직은 한 곳에서만 관리
- guide line / snap axis / threshold를 분리해서 관리

### 5. main.py 직접 실행 불가
사용자는 `python main.py` 실행을 원한다.

반드시 유지:
- 루트 `main.py`
- `run_main.bat`
- `python -m doc_capture_proto.main`
- `python main.py`

둘 다 동작해야 한다.

---

## 사용자 요구의 핵심 우선순위

### 최상위 우선순위
1. **캡쳐 정확도**
   - capture box 안의 실제 보이는 내용을 기준으로 캡쳐
   - 픽셀 추적 후 조금 여유 두고 저장
   - 이 기능 절대 제거 금지

2. **HERE 편집 안정성**
   - 선택
   - 방향키 이동
   - delete
   - copy/paste
   - resize
   - magnet
   - page 전환 후 상태 유지

3. **포커스 충돌 제거**
   - HERE 작업 중 CLIPBOARD가 활성화되면 안 됨

4. **DOCX는 반드시 보여야 함**
   - 최신 문서 포맷인데 blank면 안 됨

### 중기 우선순위
5. HWP/HWPX 로더 재설계
6. 저장 포맷 안정화
7. export 품질 개선
8. 성능 최적화

---

## Codex 작업 원칙

### 1. 기능 추가보다 퇴행 방지가 우선
이 프로젝트는 이미 기능이 많고, 입력/상태/UI가 서로 얽혀 있다.  
새 기능을 넣을 때는 반드시 아래를 먼저 점검:

- 이 기능이 active panel을 바꾸는가?
- selection sync가 focus transfer로 바뀌는가?
- keyPressEvent / keyReleaseEvent / wheelEvent / mousePressEvent가 충돌하는가?
- page/document zoom state가 덮어써지는가?

### 2. “사용자 체감 기능”을 절대 빼지 말 것
특히 절대 제거 금지:
- capture box auto trim
- live preview
- HERE magnet
- page별 zoom/pan 상태
- run_main.bat
- `python main.py` 실행 경로

### 3. 임시 축약본 금지
이 프로젝트는 간단한 데모가 아니라 실제 사용자용 툴 방향이다.  
Codex는 축약본/placeholder가 아니라 **현재 구조 위에서 실제 수정**만 해야 한다.

### 4. 바꾸는 범위를 명시할 것
수정 전후로 반드시 정리:
- 어떤 파일을 수정했는가
- 어떤 기능만 바꿨는가
- 무엇은 의도적으로 안 건드렸는가

---

## HERE 설계 원칙

### 블럭 데이터에 반드시 포함할 것
각 HERE 블럭은 최소한 아래 필드를 가져야 한다.

- `image`
- `x`, `y`
- `w`, `h`
- `original_w`, `original_h`
- `source_index`
- `content_left`, `content_right`

가능하면 추가:
- `id`
- `created_at`
- `page_index`
- `z_order`

### 방향키 이동
요구사항:
- 선택 블럭에 방향키가 먹어야 한다
- auto-repeat 허용
- CLIPBOARD 방향키는 굳이 살리지 않아도 된다

원칙:
- HERE가 active panel일 때만 이동
- selection sync 때문에 focus를 뺏기지 않도록 해야 함

### copy / paste
요구사항:
- HERE에서 `Ctrl+C`, `Ctrl+V`
- 붙여넣으면 CLIPBOARD에도 새 항목 추가

원칙:
- clipboard_store와 here_page를 동시에 갱신
- source_index 일관성 유지
- undo 스냅샷 포함

### magnet
최종 목표:
- **좌/우 정렬 가이드 전용**
- 블럭의 이미지 외곽이 아니라 **실제 컨텐츠 기준선** 사용 가능하면 더 좋음
- 파란 점선 가이드 제공

금지:
- 상하 들러붙는 snap
- 가운데 정렬처럼 보이는 오동작
- threshold가 커서 멀리서도 달라붙는 현상

---

## ORIGIN 설계 원칙

### 줌/팬
요구사항:
- 마우스 커서 중심 줌
- grab-pan 자유 이동
- space와 middle mouse 동작/커서 일관성 유지
- 허공 더블클릭 시 zoom/pan 초기화

### 파일/페이지 이동
요구사항:
- 페이지 이동
- 다중 문서일 경우 파일 단위 이동
- `Ctrl + Wheel` = 파일 이동
- `Shift + Wheel` = 페이지 이동
- 상단 슬롯 표시 및 현재 문서 닫기 `x`

원칙:
- file index / page index / zoom state를 혼동하지 말 것
- 문서별 상태 보존이 필요하면 구조적으로 분리할 것

### capture
핵심:
- 사용자가 보는 영역과 실제 캡쳐 결과가 최대한 일치해야 한다
- auto trim 절대 제거 금지
- trim 후 margin만 조정 가능

---

## DOCX / DOC / HWP 로더 전략

### DOCX
우선순위:
1. Word COM -> PDF bridge (Windows + Word 설치 시)
2. `mammoth`
3. `python-docx`
4. zip/xml raw extraction

판정 기준:
- blank page면 실패
- 텍스트라도 보여야 함
- 표/문단은 최대한 유지

### DOC
우선순위:
1. Word COM
2. `textract`
3. `olefile` raw extraction

판정 기준:
- 환경 의존성이 있음을 감안
- 최소한 텍스트 preview는 나와야 함

### HWP/HWPX
단기:
- 현재 fallback 유지
- 외부 bridge가 되면 활용

중기:
- HWP 5.x 샘플 기준으로 자체 로더 구축
- 목표:
  - OLE stream read
  - section/body text parse
  - 문단/표 모델화
  - PySide6 QPainter로 page-like render

장기:
- PDF와 동일한 ORIGIN 인터페이스 통합

---

## 테스트 체크리스트

Codex는 수정 후 아래를 반드시 수동 점검해야 한다.

### 실행
- [ ] `python main.py`
- [ ] `python -m doc_capture_proto.main`
- [ ] `run_main.bat`

### ORIGIN
- [ ] PDF 로드
- [ ] 다중 문서 로드
- [ ] 페이지 이동
- [ ] 파일 이동
- [ ] 줌
- [ ] pan
- [ ] live preview
- [ ] capture box move/resize
- [ ] auto trim capture

### CLIPBOARD
- [ ] 리스트업
- [ ] 스크롤
- [ ] live preview
- [ ] drag to HERE
- [ ] delete
- [ ] help 패널 표시

### HERE
- [ ] drag drop
- [ ] selection
- [ ] direction key move
- [ ] auto-repeat move
- [ ] delete
- [ ] copy/paste
- [ ] resize
- [ ] double click reset size
- [ ] magnet snap
- [ ] guide line
- [ ] page add/delete
- [ ] page별 zoom/pan 유지

### 저장/출력
- [ ] project save
- [ ] project load
- [ ] PDF export

### 로더
- [ ] DOCX sample
- [ ] DOC sample
- [ ] HWP sample
- [ ] HWPX sample

---

## Codex에게 권장하는 작업 순서

### Phase 1: 안정화
- HERE focus 문제 완전 제거
- 방향키 이동 안정화
- magnet 로직 단순화 및 시각화
- auto trim 회귀 테스트

### Phase 2: 문서 로더 보강
- DOCX blank 문제 해결
- DOC fallback 보강
- HWP/HWPX는 샘플 기반 자체 parser 스파이크 작성

### Phase 3: 데이터 모델 정리
- HERE block dataclass화
- page state model 정리
- clipboard/source mapping 정리
- undo stack 정교화

### Phase 4: 출력 품질
- PDF export 품질
- 배치 정확도
- image serialization 최적화

---

## Codex가 피해야 할 행동

- 사용자가 명시하지 않은 정상 기능 제거
- placeholder UI만 넣고 “구현됨”이라고 간주
- focus/selection 문제를 무시한 채 signal만 연결
- 하나의 메서드를 중복 정의
- 실행 경로를 하나만 남기기
- auto trim 제거
- magnet 제거
- “외부 프로그램 필요”만 남기고 로더를 사실상 비활성화

---

## 마지막 메모

이 프로젝트는 보기보다 어렵다.  
핵심은 “문서 처리”보다 **입력 포커스, 좌표계, 뷰 상태, 블럭 생명주기**다.

Codex는 다음 질문을 항상 먼저 해야 한다.

1. 지금 고치는 기능이 ORIGIN / CLIPBOARD / HERE 중 어느 패널의 active state를 바꾸는가?
2. selection sync가 focus transfer로 변질되는가?
3. 줌/팬/페이지/문서 상태가 서로 덮어써지는가?
4. 캡쳐 결과가 사용자가 보는 것과 달라지지 않는가?
5. 기존 정상 동작을 실수로 빼지는 않았는가?

이 다섯 개를 지키면 퇴행을 많이 줄일 수 있다.
