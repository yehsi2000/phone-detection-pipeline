# Phone Detection App

Application for detecting a mobile phone in the camera frame with screen locking.

## Installation

1. Install Python 3.13.
2. Install environment: `uv venv`.
3. Activate environment: `.venv\Scripts\activate` or `source .venv/bin/activate`
4. Install dependencies: `uv sync`
5. Place the YOLO model in `models/model.onnx`.
6. Start the application: `python main.py`.
7. Start the admin panel: `python src/admin/admin_panel.py`.

## Requirements

- Windows (for MVP)
- Web camera

## Build Instructions

- Verify the application works correctly
- Delete previous builds `rmdir /S /Q dist`, `rmdir /S /Q build`
- Obfuscate main.py: `pyarmor gen main.py`
- Copy dependencies:

```
xcopy src dist\src /E /I /Y /EXCLUDE:exclude.txt
xcopy models dist\models /E /I /Y
scopy config dist\config /E /I /Y
xcopy assets dist\assets /E /I /Y
copy config.json dist\config.json
```

- Update .spec files as needed
- Build main.py `pyinstaller main.spec`
- Build admin panel `pyinstaller admin_panel.spec`
