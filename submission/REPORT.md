# Báo cáo Day 09 — Trương Thành Đức, 2A202603034

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
Pipeline kết luận **Hold** (bản nháp). Từ **224** ảnh đầu vào, bước nhận dữ liệu loại **31** ảnh (hỏng, nhỏ, trùng, rò rỉ test/val) và giữ lại **193** ảnh đưa ra dataset `clean_v1`. Sau bước sửa tự động và duyệt **80** ảnh thì không còn lỗi bắt buộc (`0` lỗi), nhưng vẫn còn **34/193** ảnh có cảnh báo chưa được duyệt (**17.6%** ≥ ngưỡng **10.0%**) nên chưa được phép Release.

## 2. Lỗi và phân việc
Số liệu lấy từ `02_error_list_v1.txt` (quét `224` ảnh ở bước 1 và `193` ảnh qua cửa vào ở bước QC vòng 1):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2/224 ảnh | Máy (intake) | Ảnh hỏng không mở được, loại ngay ở cửa vào |
| `BAD_SIZE` | 3/224 ảnh | Máy (intake) | Cạnh ngắn nhỏ hơn `250px`, không đạt chuẩn đầu vào |
| `DUP_IMAGE_EXACT` | 8/224 ảnh | Máy (intake) | Trùng từng byte (md5), loại bản sau để tránh lặp |
| `DUP_IMAGE_NEAR` | 7/224 ảnh | Máy (intake) | Trùng gần đúng (`phash <= 16`), loại bản sau |
| `LEAK_TEST` | 11/224 ảnh | Máy (intake) | Trùng ảnh trong `test`/`gold_val`, loại để tránh rò rỉ |
| `BAD_CLASS_NAME` | 2 dòng (`data.yaml`) | Máy (autofix) | Sửa lại tên lớp trong `data.yaml` đúng quy ước chữ thường |
| `BAD_CLASS_ID` | 6 dòng (193 ảnh) | Máy (autofix) | ID lớp ngoài `0..3` (`-1, 4, 7, 93`), xóa dòng an toàn |
| `BAD_FORMAT` | 3 dòng (193 ảnh) | Máy (autofix) | Dòng thiếu cột hoặc chứa `nan`, xóa dòng |
| `BOX_ZERO` | 4 dòng (193 ảnh) | Máy (autofix) | Box rộng hoặc cao bằng `0`, không có diện tích nên xóa |
| `DUP_BOX` | 7 dòng (193 ảnh) | Máy (autofix) | Hai box cùng lớp gần như trùng (`IoU > 0.9`), xóa dòng sau |
| `BOX_OUT_OF_IMAGE` | 8 dòng (193 ảnh) | Máy (autofix) | Cắt tọa độ box tràn mép về trong `[0, 1]` |
| `MISSING_LABEL_FILE` | 6/193 ảnh | Người | Máy không tự bịa nhãn được, đẩy lên đầu hàng đợi cho người gán |
| `EMPTY_LABEL` | 11/193 ảnh | Người | Cần nhìn ảnh để biết là ảnh nền thật hay bị sót nhãn |
| `BOX_TINY` | 6 dòng (193 ảnh) | Người | Box cạnh ngắn `< 12px`, người xem nên giữ hay xóa nhiễu |
| `BOX_HUGE` | 3 dòng (193 ảnh) | Người | Box chiếm `> 95%` diện tích ảnh, cần người kiểm lại |
| `CLASS_RARE` | 4 mã lớp | Người | Cảnh báo các token lớp có `< 5` box (do 4 ID lạ trước khi autofix) |
| `POSSIBLE_MISSING` | 53 box (193 ảnh) | Người | Model `yolo26l` nghi sót vật thể, cần người đối chiếu ảnh |
| `POSSIBLE_LOOSE_BOX` | 27 box (193 ảnh) | Người | Box khớp vật nhưng `IoU < 0.5`, cần người chỉnh lại mép |
| `POSSIBLE_WRONG_CLASS` | 17 box (193 ảnh) | Người | Model dự đoán lớp khác (`IoU >= 0.5`), cần người quyết định lớp đúng |
| `POSSIBLE_FALSE_POS` | 28 box (193 ảnh) | Người | Box nhãn không khớp dự đoán nào của model, cần người kiểm tra thừa |

`05_review_queue.csv` sắp xếp theo tổng điểm ưu tiên: ảnh thiếu file nhãn được gán trọng số cao (`NEEDS_LABEL = 10`) để không làm tắc gate Rework, còn các ảnh có nhiều cảnh báo ngữ nghĩa độ tin cậy cao hoặc vừa bị autofix xóa/cắt dòng sẽ bị cộng dồn điểm (như `img_0020` đạt `11.524` điểm nên đứng đầu, ngay sau là `6` ảnh `NEEDS_LABEL` `10.0` điểm). Với ngân sách **80** ảnh trên tổng **121** ảnh hàng đợi, người duyệt xử lý được **6** ảnh thiếu nhãn và **94/120** lỗi ngữ nghĩa (trên **74/100** ảnh có cảnh báo ngữ nghĩa; còn **26/100** ảnh ngữ nghĩa chưa tới lượt).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | DUP_IMAGE_NEAR 1.00 / 0.50 / 0.67 -> DUP_IMAGE_NEAR 1.00 / 0.83 / 0.91 | Giữ Precision 1.00 để tránh xóa nhầm ảnh sạch, tăng Recall bắt thêm ảnh gần trùng. Không tăng lên 20 vì dễ gộp nhầm sang tập test/val. |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS  0.56 / 0.83 / 0.67  MISSING      0.50 / 1.00 / 0.67  LOOSE_BOX    0.29 / 0.40 / 0.33 ->  WRONG_CLASS  0.62 / 0.83 / 0.71  MISSING      0.57 / 1.00 / 0.73  LOOSE_BOX    0.20 / 0.20 / 0.20| Giữ được Recall cao để không bỏ sót lỗi thiếu nhãn/nhầm lớp (lên 0.7–0.8 sẽ sót), đồng thời tăng Precision để giảm báo động giả cho người duyệt (chấp nhận LOOSE_BOX giảm R 0.40→0.20). |

**một chỗ calibration có thể đánh lừa bạn** Bộ calib chỉ có 39 ảnh (mỗi loại lỗi chỉ có vài mẫu nên chỉ cần lệch 1 ảnh là Precision/Recall nhảy ~17–20%), và không có lỗi LEAK_TEST trong đáp án như dữ liệu thật. Cụ thể, phash_dist = 16 đạt Precision = 1.00 rất đẹp trên calib, nhưng khi đưa sang data/raw (224 ảnh) thì số ảnh bị loại ở bước 1 tăng lên 31 ảnh: riêng ở khoảng cách dist = 16, LEAK_TEST nhảy từ 5 lên 11 ảnh và DUP_IMAGE_NEAR từ 4 lên 7 ảnh, bắt nhầm cả những cặp khác nội dung nhãn như img_0011 (1 person) với img_0008 (2 person) hoặc img_0177 (person + bus) với img_0113 (person, ảnh vốn đã bị loại vì nhỏ). Vì vậy không nên tin tuyệt đối ngưỡng tối ưu trên calib mà cần kiểm tra lại trên raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **(a) Chứng minh cửa chặn hoạt động đúng:** Khi chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt), `6` ảnh `MISSING_LABEL_FILE` vẫn chưa có nhãn nên `work/rep_nb/08_summary.json` kết luận **Rework** (`n_errors = 6`, `108/193` ảnh có cảnh báo chưa duyệt), mã thoát là **20**, và thư mục `work/exp_nb/clean_v1/` **không được xuất** (`exported: null`).
- **(b) Các điểm mù pipeline không bắt được:**
  1. **Box lỏng nhẹ (`IoU >= 0.5`):** Do `second_opinion.iou_loose = 0.5` là ngưỡng cố định trong `configs/pipeline.yaml`, các box vẽ hơi lệch/rộng nhưng vẫn khớp model với `IoU` từ `0.5` trở lên sẽ không bị cảnh báo `POSSIBLE_LOOSE_BOX`.
  2. **Vật quá nhỏ hoặc lỗi mà `yolo26l` cũng không thấy (`< 600 px²` hoặc `conf < 0.6`):** `second_opinion` bỏ qua dự đoán nhỏ hơn `600 px²` và dưới `conf = 0.6`, nên các vật nhỏ bị thiếu nhãn hoặc ca nhầm lớp mà model lớn cũng dự đoán nhầm/không tự tin sẽ lọt qua (trên `calib` ở `conf = 0.6`, `WRONG_CLASS` vẫn sót `1/6` lỗi với `Recall = 0.83`).
  3. **Ảnh gần trùng biến đổi mạnh:** Trên `calib` với `phash_dist = 16`, vẫn còn `1/6` ca `DUP_IMAGE_NEAR` bị bỏ sót (`Recall = 0.83`) khi ảnh bị cắt hoặc biến đổi làm khoảng cách `phash` vượt quá `16`.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy do chưa có thời gian ạ

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".
- **(a) Quyết định cuối:** Pipeline kết luận **Hold** vì tuy không còn lỗi bắt buộc (`0` lỗi), nhưng sau khi duyệt hết ngân sách `80` ảnh thì vẫn còn `34/193` ảnh có cảnh báo chưa duyệt (`17.6% >= 10.0%`). Để chuyển thành **Release**, cần duyệt thêm ít nhất **15** ảnh cảnh báo nữa (nâng ngân sách lên khoảng `95` ảnh để kéo tỉ lệ xuống tối đa `19/193` ảnh, tức `< 10%`), không nâng ngưỡng quá cao để tránh bỏ sót lỗi thật.
- **(b) Ghi chú dùng AI:**
  - *Prompt chính:* Dán docstring và file test của từng module (`label_format`, `gate`, `autofix`, `second_opinion`), yêu cầu đọc ngưỡng từ `cfg`, giữ nguyên số dòng gốc khi có dòng trống/lỗi và không sửa `data/raw` hay `tests/`.
  - *Cách kiểm code AI:* Đọc lại code để chắc không hardcode ngưỡng hay `except: pass`, chạy `python -m pytest -q` qua đủ 79 test, rồi tự thử thêm mấy ca biên (1 dòng 2 lỗi, dòng hỏng trước `FALSE_POS`) và kiểm tra khi chạy thật trên `calib`/`raw`.
  - *Một lần AI sai/thừa:* Lúc mình chỉ bảo sửa 4 file code ở bước 2, AI lại chạy thêm `pipeline.run` làm sinh ra hàng loạt file trong `submission/` ngoài phạm vi; mình thấy file lạ hiện trên git nên đã yêu cầu xóa hết để giữ đúng 4 file.
