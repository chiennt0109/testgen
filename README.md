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
2. Trong **Input Schema**, chọn loại block rồi bấm **Thêm block**. Chọn từng
   block ở danh sách bên trái và nhập tên, min/max, length, pattern cùng cách
   xuống dòng trong form bên phải. Ví dụ để tạo `n k` và mảng `a`, lần lượt thêm:
   - `Integer n`: min `1`, max `100`, chọn **Ghép cùng dòng**;
   - `Integer k`: min `1`, max `n`, bật **Xuống dòng sau block này**;
   - `Array a`: length `n`, min `-100`, max `100`, pattern tùy chọn.

   Có thể nhân bản, xóa và đổi thứ tự block bằng các nút ngay trên danh sách.
   Trường nâng cao vẫn nhận một object JSON nhỏ nhưng không bắt buộc cho workflow
   thông thường.

### Query List và Operation List

Chọn block `Query List` rồi bấm **Chỉnh cấu trúc query…** để khai báo một hoặc
nhiều query type. Mỗi type có tên, weight, fixed prefix/type code và bảng field.
Field được sinh từ trái sang phải, vì vậy có thể nhập `r.min = l`, `r.max = n`
hoặc tham chiếu bất kỳ biến đã sinh trước đó. Dialog cũng cấu hình duplicate
policy, thứ tự query và lựa chọn **Mỗi query một dòng** hoặc ghép cùng dòng.

Ví dụ range query dùng hai field `l: Integer [1,n]` và
`r: Integer [l,n]`. Operation trộn có thể dùng type prefix `1` với fields `i,x`
weight 40%, và prefix `2` với fields `l,r` weight 60%. Preset hoàn chỉnh nằm tại
`presets/range_sum.json`.
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

Core V1 hỗ trợ scalar, array, string, graph/weighted graph, tree/weighted tree,
query/interval và raw block; runner hỗ trợ C++, Python, executable, STDIO và
`freopen` file mode. GUI có form General, visual Input Schema Builder, Test Plan,
Subtasks, Solution/compiler, Validator, Stress Test, Analyze và Export. Các tác vụ
dài chạy nền với progress/cancel; Basic Mode ẩn các trang nâng cao nhưng vẫn dùng
chung service layer với Advanced Mode.
