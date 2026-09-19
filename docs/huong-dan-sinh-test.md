# Hướng dẫn sinh test với Test Generator Studio

Tài liệu này mô tả quy trình từ lúc tạo project đến khi có ZIP bộ test. Nên làm
theo thứ tự để lỗi constraint hoặc solution được phát hiện trước khi sinh cả batch.

## 1. Chuẩn bị

1. Cài Python 3.12+, `pip install -r requirements.txt` và chạy `python main.py`.
2. Nếu dùng C++, cài `g++`, thêm vào `PATH` hoặc chọn file `g++.exe` tại trang
   **Solution**.
3. Chọn **Advanced Mode** để thấy Subtasks, Validator, Stress Test, Analyze và Export.

## 2. Tạo và lưu project

1. Bấm **New Project**.
2. Tại **General**, nhập tên bài, tên `.inp/.out`, số test, seed, time limit và
   memory limit.
3. Bấm **Save As** và lưu `project.json` trong thư mục riêng của bài. Các đường
   dẫn solution, brute và validator tương đối sẽ được tính từ thư mục này.

Nên lưu project trước khi chọn source code hoặc Generate All. Cùng project, seed
và phiên bản app sẽ tái tạo cùng input.

## 3. Khai báo Input Schema

Tại **Input Schema**, thêm block theo đúng thứ tự xuất hiện trong input.

Ví dụ `n k` ở dòng đầu và mảng ở dòng sau:

1. `Integer n`: Min `1`, Max `100000`, chọn **Ghép cùng dòng**.
2. `Integer k`: Min `1`, Max `n`, bật xuống dòng.
3. `Array a`: Length `n`, Min/Max và pattern mong muốn.

Với Query List, bấm **Chỉnh cấu trúc query…**, tạo query type và field. Ví dụ
range query gồm `l: 1..n`, `r: l..n`; chọn **Mỗi query một dòng**. Với operation
trộn, dùng prefix `1`/`2` và weight tương ứng.

Sau mỗi thay đổi, chọn **Test #** cạnh Preview rồi bấm **Generate Preview**. Preview
dùng đúng group Test Plan và mọi Subtask chứa test đó; dòng trạng thái hiển thị
Group/Subtasks đã áp dụng. Có thể Regenerate, Copy hoặc Save This Test.

## 4. Lập Test Plan

Tại **Test Plan**:

1. Bấm **Thêm nhóm** cho từng nhóm Edge, Small, Medium, Large hoặc Adversarial.
2. Nhập số test và profile.
3. Chọn nhóm, bấm **Chỉnh constraints…**.
4. Tick biến cần override và nhập **Exact**, **Min**, **Max**, **Length/Count**
   hoặc **Pattern**. Không nhập JSON.

Ví dụ nhóm Small đặt `n.max = 100`; nhóm Max đặt `n.exact = 100000`. Tổng số
test trong các group nên bằng Test count. Nếu thiếu, app bổ sung nhóm Random; nếu
thừa, danh sách được cắt theo Test count.

**Number of tests là số test liên tiếp của group, không phải số thứ tự group.**
Nếu Subtask 1 là test 01–06, Subtask 2 là 07–13 và Subtask 3 là 14–20 thì ba
group tương ứng thường phải có Number of tests là `6`, `7`, `7` — không phải
`1`, `1`, `1`. Nếu nhập `1`, `1`, `1`, chỉ test01–03 dùng ba group đó và test04–20
sẽ được bổ sung bằng Random.

## 5. Khai báo Subtasks

Tại **Subtasks**:

1. Bấm **Thêm subtask**, nhập tên và khoảng test inclusive, ví dụ `1` đến `5`.
2. Chọn dòng và bấm **Chỉnh constraints…**.
3. Chọn biến rồi nhập giới hạn giống Test Plan.

Test Plan chọn profile và constraint ban đầu. Với mỗi test, app lấy mọi Subtask
chứa test đó rồi **giao constraint của Subtask với Test Plan trước khi sinh**. Ví
dụ group cho `n=1..1000`, Subtask cho `n<=100` thì generator dùng `n=1..100` ngay
từ đầu. Sau khi sinh, app vẫn validate lần thứ hai để bảo vệ custom generator hoặc
pattern không tuân thủ constraint.

## 6. Cấu hình solution và validator

Tại **Solution**:

1. Chọn `solution.cpp`, `.py` hoặc `.exe`; chọn C++17/C++20 nếu cần.
2. Chọn **STDIN / STDOUT** hoặc **File I/O (freopen)**.
3. Chọn `g++` nếu app không tìm thấy và bấm **Test Compiler**.
4. Chọn `brute.cpp`/`.py` nếu muốn Cross Check.
5. Bật **Sinh file .out trong Generate All** khi solution đã chạy đúng. Nếu đang
   thiết kế input hoặc solution còn lỗi, bỏ chọn mục này để sinh riêng `.inp`, sau
   đó sửa solution và dùng **Build Output**.

Tại **Validator**, có thể chọn `validator.py` với API:

```python
def validate(input_text: str, params: dict):
    return True, ""
```

Bấm **Validate** để kiểm tra preview hoặc batch hiện có.

## 7. Sinh toàn bộ test

1. Save project.
2. Generate Preview và kiểm tra ít nhất một test.
3. Bấm **Generate All**.
4. Theo dõi progress; bấm **Hủy** nếu cần. Việc hủy là cooperative nên compile
   hoặc process đang chạy có thể cần kết thúc trước.

Pipeline tạo thư mục tạm, generate, validate, kiểm tra subtask/duplicate, chạy
solution và chỉ publish khi toàn bộ thành công. Nếu output đã tồn tại, app tạo
`_V02`, `_V03`,… thay vì ghi đè.

Trước khi chạy, app kiểm tra tổng Number of tests và giao giữa constraint của Test
Plan/Subtask. Ví dụ group đặt `n.min=2000` nhưng subtask chứa test đó đặt
`n.max=1999` sẽ bị chặn và chỉ rõ test/group bị xung đột. Nếu tổng group khác Test
count, app cảnh báo rằng phần thiếu sẽ dùng Random hoặc phần dư sẽ bị cắt.

Kết quả:

```text
generated/TENBAI/
├── test01/TENBAI.inp
├── test01/TENBAI.out
└── manifest.json
```

Nếu đã có input nhưng chưa có output, bấm **Build Output**.

## 8. Stress Test

1. Cấu hình cả Solution và Brute.
2. Chọn iterations, generator profile và timeout.
3. Bấm **Start Cross Check**; không bấm lại trong khi task đang chạy.
4. Bấm **Stop** để yêu cầu dừng.

App compile mỗi chương trình một lần trong thư mục tạm. Nếu output khác nhau hoặc
một chương trình lỗi, input và hai output được lưu tại
`counterexamples/seed_<seed>/`. Sau khi task kết thúc có thể chạy lại ngay; app
không tái sử dụng `QThread` đã bị Qt giải phóng.

## 9. Analyze và Export

1. Bấm **Analyze** để xem min/max/mean và các cảnh báo coverage.
2. Tại **Export**, kiểm tra generated folder và bấm **Export ZIP**.
3. Dùng **Open Output Folder** để kiểm tra trực tiếp cây test.

ZIP chỉ chứa bộ test/manifest, không chứa cache hoặc thư mục tạm.

## 10. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
| --- | --- |
| `Constraint Error` | Kiểm tra min ≤ max và biến tham chiếu đã nằm trước block hiện tại. |
| `Compile Error` | Bấm Test Compiler, kiểm tra đường dẫn g++ và chuẩn C++. |
| `Runtime Error` / `Timeout` | Chạy solution với preview, tăng timeout nếu hợp lý. |
| `Output Missing` | Với freopen, kiểm tra chính xác tên input/output trong General. |
| `Subtask Constraint Error` | Sửa Test Plan override hoặc constraint/range của Subtask. |
| `Duplicate Input` | Đổi policy hoặc tăng miền dữ liệu/seed profile. |
| Stress lưu counterexample | Mở ba file trong `counterexamples/seed_*` để debug. |

Khi Generate All gặp Runtime Error, app lưu input gây lỗi, `stdout.txt`,
`stderr.txt` và `run.json` tại `generation_failures/testXX[_VNN]/`. Nếu solution
dùng `freopen` nhưng trang Solution đang chọn STDIN/STDOUT, chuyển sang **File I/O**
và đảm bảo tên trong `freopen` khớp chính xác Input/Output filename ở General.
Exit code Windows `3221225781` (`0xC0000135`) nghĩa là thiếu DLL runtime. App hiện
liên kết tĩnh MinGW runtime khi compile trên Windows; hãy Generate All/Build Output
lại, hoặc thêm thư mục `bin` của MinGW vào `PATH` nếu đang chạy executable cũ.

Nếu task nền đã kết thúc, có thể chạy Generate/Stress/Analyze tiếp theo ngay. Nếu
đang chạy, app báo **Một tác vụ nền đang chạy** thay vì tạo thêm thread song song.
