# Báo cáo Day 09 — Trương Thành Đức, 2A202603034

## 1. Kết luận trước
Pipeline kết luận **Hold** (bản nháp). Trong 224 ảnh đầu vào từ `data/raw/`, bước nhận dữ liệu loại 31 ảnh (ảnh hỏng, nhỏ, trùng và rò rỉ với test/val), còn lại 193 ảnh đưa vào dataset `clean_v1`. Sau khi máy tự sửa hết lỗi bắt buộc (`0` lỗi) và người duyệt xem xong 80 ảnh, vẫn còn 34/193 ảnh có cảnh báo chưa được duyệt (17.6%, vượt ngưỡng 10.0%) nên chưa thể Release.

## 2. Lỗi và phân việc
Số liệu thống kê từ `02_error_list_v1.txt` (quét 224 ảnh ở cửa vào và 193 ảnh qua bước QC vòng 1):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2/224 ảnh | Máy (intake) | Ảnh hỏng không mở được, loại ngay ở cửa vào |
| `BAD_SIZE` | 3/224 ảnh | Máy (intake) | Cạnh ngắn nhỏ hơn `250px`, không đạt chuẩn đầu vào |
| `DUP_IMAGE_EXACT` | 8/224 ảnh | Máy (intake) | Trùng từng byte (md5), loại bản sau để tránh lặp |
| `DUP_IMAGE_NEAR` | 7/224 ảnh | Máy (intake) | Trùng gần đúng (`phash <= 16`), loại bản sau |
| `LEAK_TEST` | 11/224 ảnh | Máy (intake) | Trùng ảnh trong `test`/`gold_val`, loại để tránh rò rỉ |
| `BAD_CLASS_NAME` | 2 dòng (`data.yaml`) | Máy (autofix) | Sửa lại tên lớp trong `data.yaml` đúng chữ thường |
| `BAD_CLASS_ID` | 6 dòng (193 ảnh) | Máy (autofix) | ID lớp ngoài `0..3` (`-1, 4, 7, 93`), xóa dòng là an toàn |
| `BAD_FORMAT` | 3 dòng (193 ảnh) | Máy (autofix) | Dòng thiếu cột hoặc có `nan`, xóa dòng |
| `BOX_ZERO` | 4 dòng (193 ảnh) | Máy (autofix) | Box rộng hoặc cao bằng 0 nên xóa |
| `DUP_BOX` | 7 dòng (193 ảnh) | Máy (autofix) | Hai box cùng lớp gần như trùng (`IoU > 0.9`), xóa dòng sau |
| `BOX_OUT_OF_IMAGE` | 8 dòng (193 ảnh) | Máy (autofix) | Cắt tọa độ box tràn mép về trong `[0, 1]` |
| `MISSING_LABEL_FILE` | 6/193 ảnh | Người | Máy không tự gán nhãn được, đẩy lên đầu hàng đợi |
| `EMPTY_LABEL` | 11/193 ảnh | Người | Cần nhìn ảnh xem là ảnh nền thật hay bị thiếu nhãn |
| `BOX_TINY` | 6 dòng (193 ảnh) | Người | Box cạnh ngắn `< 12px`, người xem nên giữ hay bỏ |
| `BOX_HUGE` | 3 dòng (193 ảnh) | Người | Box chiếm `> 95%` diện tích ảnh, cần người kiểm tra lại |
| `CLASS_RARE` | 4 mã lớp | Người | Cảnh báo các token lớp có `< 5` box (do 4 ID lạ trước khi autofix) |
| `POSSIBLE_MISSING` | 53 box (193 ảnh) | Người | Model `yolo26l` nghi sót vật thể, cần người đối chiếu ảnh |
| `POSSIBLE_LOOSE_BOX` | 27 box (193 ảnh) | Người | Box khớp vật nhưng `IoU < 0.5`, cần người chỉnh lại |
| `POSSIBLE_WRONG_CLASS` | 17 box (193 ảnh) | Người | Model dự đoán lớp khác (`IoU >= 0.5`), cần người chốt lớp đúng |
| `POSSIBLE_FALSE_POS` | 28 box (193 ảnh) | Người | Box nhãn không khớp dự đoán nào, cần người kiểm tra xem có thừa không |

`05_review_queue.csv` xếp ưu tiên theo tổng trọng số các lỗi: ảnh thiếu file nhãn được cộng `10` điểm (`NEEDS_LABEL`) để không bị mắc ở gate Rework, còn ảnh dính nhiều cảnh báo ngữ nghĩa độ tin cậy cao hoặc vừa bị autofix cắt/xóa dòng sẽ bị cộng dồn điểm (nên `img_0020` lên đầu với `11.524` điểm, tiếp theo là 6 ảnh `NEEDS_LABEL` mức `10.0` điểm). Với ngân sách 80 ảnh trên tổng 121 ảnh trong hàng đợi, người duyệt xem được 6 ảnh thiếu file nhãn và 94/120 lỗi ngữ nghĩa (nằm trên 74/100 ảnh có cảnh báo ngữ nghĩa; còn 26/100 ảnh chưa tới lượt).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | `DUP_IMAGE_NEAR`: P `1.00→1.00`, R `0.50→0.83`, F1 `0.67→0.91` | Giữ Precision 1.00 để tránh xóa nhầm ảnh sạch, tăng Recall bắt thêm ảnh gần trùng. Không tăng lên 20 vì dễ gộp nhầm sang tập test/val. |
| `second_opinion.conf` | 0.25 | 0.6 | `WRONG_CLASS`: P `0.56→0.62`, R `0.83→0.83`; `MISSING`: P `0.50→0.57`, R `1.00→1.00`; `LOOSE_BOX`: P `0.29→0.20`, R `0.40→0.20` | Giữ được Recall cao để không bỏ sót lỗi thiếu nhãn/nhầm lớp (lên 0.7–0.8 sẽ sót), đồng thời tăng Precision giảm báo động giả cho người duyệt (chấp nhận `LOOSE_BOX` giảm R `0.40→0.20`). |

Điểm dễ bị đánh lừa khi calibrate là bộ `calib` chỉ có 39 ảnh (mỗi loại lỗi có vài mẫu nên lệch 1 ảnh là Precision/Recall nhảy ~17–20%) và cũng không có ca `LEAK_TEST` trong đáp án như dữ liệu thật. Trên `calib`, mức `phash_dist = 16` đạt Precision 1.00 rất đẹp, nhưng khi chạy sang `data/raw` (224 ảnh) thì số ảnh bị loại ở bước 1 tăng lên 31 ảnh: riêng ở `dist = 16`, `LEAK_TEST` nhảy từ 5 lên 11 ảnh và `DUP_IMAGE_NEAR` từ 4 lên 7 ảnh, bắt nhầm cả những cặp khác nội dung như `img_0011` (1 `person`) với `img_0008` (2 `person`) hay `img_0177` (`person` + `bus`) với `img_0113` (`person`, ảnh vốn bị loại vì nhỏ). Vì vậy không nên tin hoàn toàn vào ngưỡng tối ưu trên `calib` mà phải kiểm tra lại trên `raw`.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Khi chạy thử với ngân sách bằng 0 (`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`), 6 ảnh `MISSING_LABEL_FILE` vẫn chưa có nhãn nên `work/rep_nb/08_summary.json` kết luận **Rework** (`n_errors = 6`, còn 108/193 ảnh có cảnh báo chưa duyệt), mã thoát là `20` và thư mục `work/exp_nb/clean_v1/` không được xuất (`exported: null`).

Một số lỗi pipeline vẫn bỏ lọt:
- Box lỏng nhẹ: vì `second_opinion.iou_loose = 0.5` cố định trong `configs/pipeline.yaml`, các box gán hơi rộng/lệch nhưng vẫn có `IoU >= 0.5` với dự đoán của model sẽ không bị cảnh báo `POSSIBLE_LOOSE_BOX`.
- Vật nhỏ hoặc ca mà `yolo26l` cũng sai/không chắc: `second_opinion` bỏ qua dự đoán diện tích `< 600 px²` và `conf < 0.6`, nên các vật nhỏ bị sót hoặc lỗi nhầm lớp mà model lớn cũng dự đoán sai/tự tin thấp sẽ lọt qua (trên `calib` ở `conf = 0.6`, `WRONG_CLASS` vẫn sót 1/6 ca với Recall `0.83`).
- Ảnh gần trùng biến đổi mạnh: ở `phash_dist = 16`, trên `calib` vẫn sót 1/6 ca `DUP_IMAGE_NEAR` (Recall `0.83`) khi ảnh bị cắt hoặc biến đổi nhiều hơn ngưỡng 16.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (chưa có điều kiện train GPU trên Google Colab).

## 6. Quyết định và ghi chú AI
Pipeline kết luận **Hold** vì dù hết lỗi bắt buộc (0 lỗi) nhưng sau khi dùng hết ngân sách 80 ảnh duyệt thì vẫn còn 34/193 ảnh có cảnh báo chưa được xem (17.6% >= 10.0%). Để chuyển sang **Release**, cần duyệt thêm ít nhất 15 ảnh cảnh báo nữa (tăng ngân sách lên khoảng 95 ảnh để kéo tỉ lệ xuống tối đa 19/193 ảnh, tức `< 10%`), không nên kéo ngưỡng `conf` lên quá cao chỉ để làm rỗng hàng đợi giả.

Ghi chú dùng AI:
- Prompt chính: dán docstring và file test của từng module (`label_format`, `gate`, `autofix`, `second_opinion`), yêu cầu đọc ngưỡng từ `cfg`, giữ nguyên số dòng gốc khi có dòng trống/lỗi và không sửa `data/raw` hay `tests/`.
- Cách kiểm code AI: đọc lại code để chắc không viết cứng ngưỡng hay dùng `except: pass`, chạy `python -m pytest -q` qua đủ 79 test, rồi tự thử thêm mấy ca biên (1 dòng 2 lỗi, dòng hỏng trước `FALSE_POS`) và kiểm tra kết quả khi chạy thật trên `calib`/`raw`.
- Một lần AI sai/thừa: lúc mình chỉ giao sửa 4 file code ở bước 2, AI tự chạy thêm `pipeline.run` làm sinh ra hàng loạt file trong `submission/` ngoài phạm vi; mình thấy file lạ hiện trên git nên yêu cầu xóa hết để giữ đúng 4 file.
