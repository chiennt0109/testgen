# Test Generator Studio

Ứng dụng desktop offline, deterministic để thiết kế và xuất bộ test thi lập trình. Backend tách khỏi PySide6 GUI: schema blocks, constraint engine, test plan, validation, SHA-256 duplicate detection, transactional generation, solution runner và ZIP export.

## Cài môi trường phát triển

Yêu cầu Python 3.12+, và `g++` trong `PATH` nếu chạy lời giải C++.

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt
python main.py
```

Linux/macOS dùng `source .venv/bin/activate`. App ghi lỗi vào `logs/app.log`.

## Workflow

1. Chọn **New Project**, nhập tên bài và số test.
2. Trong **Input Schema**, nhập mảng JSON block. Ví dụ `n k` trên dòng đầu và mảng trên dòng sau:
   ```json
   [
     {"type":"integer","name":"n","min":1,"max":100,"layout":"same_line"},
     {"type":"integer","name":"k","min":1,"max":"n","newline":true},
     {"type":"array","name":"a","length":"n","min":-100,"max":100}
   ]
   ```
3. **Generate Preview** kiểm tra dữ liệu trong bộ nhớ; **Save As** lưu `project.json`.
4. Đặt `solution.cpp` cạnh project. **Generate All** compile một lần, validate và xuất `.inp/.out`, rồi mới publish cả batch. Nếu đích đã tồn tại, app tạo `_V02` thay vì ghi đè.
5. Manifest lưu seed riêng (`master_seed + index`) và SHA-256. Mở lại cùng project sẽ tái tạo input giống nhau.
6. Dùng API `SolutionRunner` cho stress/cross-check; demo có cả `solution.cpp` và `brute.cpp`.
7. Dùng `app.exporters.export_zip` để xuất ZIP giữ nguyên cây thư mục.

## Custom generator và validator

`generator.py` cung cấp `generate(seed: int, params: dict) -> str`; `validator.py` cung cấp `validate(input_text, params) -> (bool, str)`. Exception được chuyển thành lỗi có ngữ cảnh thay vì làm crash GUI. Xem project hoàn chỉnh tại `examples/MAXSEQ/`, gồm 10 profile từ edge case đến random lớn.

## Kiểm thử

```bash
pytest -q
QT_QPA_PLATFORM=offscreen timeout 3 python main.py
```

Tests bao phủ constraint an toàn, array patterns, graph liên thông/simple, các tree pattern, query ranges, reproducibility, duplicate manifest và ZIP layout.

## Build Windows

```bat
build.bat
```

PyInstaller tạo bản `onedir` tại `dist/TestGeneratorStudio/TestGeneratorStudio.exe` và đóng kèm preset. Compiler MinGW không được tải tự động; cài riêng và thêm `g++` vào `PATH`.

## Phạm vi hiện tại

Core V1 hỗ trợ scalar, array, string, graph/weighted graph, tree/weighted tree, query/interval và raw block; runner hỗ trợ C++, Python, executable, STDIO và `freopen` file mode. GUI cung cấp shell điều hướng, General, JSON schema editor, preview/save/open và batch background có progress. Các màn hình chỉnh sửa trực quan chuyên sâu cho operation/matrix, quản lý preset, subtasks, analyzer, ZIP và stress statistics sẽ tiếp tục dùng cùng service layer thay vì tạo code path riêng.
