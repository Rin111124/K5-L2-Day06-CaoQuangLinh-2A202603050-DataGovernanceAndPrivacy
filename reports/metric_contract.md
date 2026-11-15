# Metric contract T05

Đây là protocol đề xuất, cần nhóm xác nhận và chốt trước khi đánh giá. Không
điều chỉnh ngưỡng theo GT của giảng viên.

| Mục | Protocol |
|---|---|
| Track | T05 — Leakage & Near-Duplicate Guardian |
| Metric chính | Leakage Detection F1 (pair), càng cao càng tốt |
| Đơn vị | Cặp không thứ tự của `image_id` |
| Công thức | Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2PR/(P+R) |
| Quy tắc khớp | Cặp dự đoán là dương tính khi hai ID cùng `dup_group_id` trong GT; bỏ qua thứ tự cặp |
| Candidate pool | Mọi cặp không thứ tự từ `fixtures/t05_near_duplicate/images.csv` |
| Review budget / seed | B = 20; seed = 42 |
| Quy tắc dự đoán dương tính | SHA-256 trùng, hoặc tương quan ảnh xám chuẩn hóa >= 0.92, hoặc tương quan >= 0.78 cùng pHash Hamming <= 8 và dHash Hamming <= 12 |
| Quy tắc đưa vào review | Tương quan >= 0.70 và pHash Hamming <= 16; reviewer có thể approve hoặc reject |
| Quy tắc chia split | Gom cạnh dự đoán dương tính và ảnh cùng camera chụp cách nhau <= 60 giây; chia component 70/30 train/test với seed 42 |
| Dữ liệu đánh giá | Chỉ dùng GT overlay của giảng viên. Pipeline không đọc GT và không tune trên GT. GT chưa có trong checkout này nên đánh giá chính thức đang chờ |
| Chỉ số lỗi | False merge rate và residual cross-split near-duplicate leakage |
| Slice dự kiến | Exact hash so với visual candidate; camera và burst nếu số lượng đủ |
| Độ bất định | Khi có GT, báo cáo số lượng và bootstrap interval theo duplicate group; kết quả fixture chỉ mang tính chẩn đoán |
| Người/ngày chốt ngưỡng | Cao Quang Linh (owner) — 15/11/2026 (đã chốt và đóng băng trước khi đánh giá trên ground truth ẩn) |

Baseline dùng exact-hash và chia ngẫu nhiên theo từng ảnh. PoC gom các cặp
near-duplicate dự đoán cùng burst cùng camera trước khi chia train/test. Cả hai
pipeline đều không đọc ground truth của giảng viên.
