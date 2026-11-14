# Tiến độ bài lab Day 06

Trạng thái: ✅ xong · 🔄 đang làm · ⏸️ chờ học viên · ⬜ chưa làm

## Quyết định đã chốt

| Hạng mục | Lựa chọn | Lý do |
|---|---|---|
| Corpus | Datio English, *Xây nền ngữ pháp trong 30 ngày* (47 trang PDF, tính 40 trang nội dung) | Text trích xuất được, metadata tuần/ngày/loại trang in sẵn trên trang |
| Embedding | `intfloat/multilingual-e5-small` (local, 384 chiều, 512 token, chi phí 0) | Hỗ trợ tiếng Việt. GV gợi ý `all-MiniLM-L6-v2` nhưng model đó chỉ hỗ trợ tiếng Anh. |
| Vector store | Chroma 1.5.9, `PersistentClient` tại `starter/chroma_db/`, cosine, HNSW (approximate) | Máy không có Docker nên không chạy được pgvector |
| A | `fixed_size(500, overlap 50)`, không lọc | |
| B | `by_paragraph(max 800)`: tách theo heading của workbook, không lọc | A và B chỉ khác cách chunk |
| C | Cùng index với B, lọc metadata khi câu hỏi có `filter` | B và C chỉ khác bước lọc |
| Trường lọc | `page_type`, `week`, `day_start`, `day_end` (lấy từ nhãn in trên trang) | |

## Quy trình

| # | Bước | Trạng thái | Đầu ra |
|---|---|---|---|
| 0 | Cài môi trường (`starter/.venv`) | ✅ | [starter/requirements.txt](starter/requirements.txt) |
| 1 | Chọn corpus, đếm trang, manifest | ✅ (nguồn ieltsdatio.edu.vn, tải ngày 2026-11-14) | [data/manifest.json](data/manifest.json) |
| 2 | Đọc và chuẩn hóa PDF, log lỗi | ✅ | [starter/src/ingestion.py](starter/src/ingestion.py) |
| 3 | Viết 20 câu benchmark và kiểm tra evidence tự động | ✅ bản nháp | [benchmark/questions.json](benchmark/questions.json), [starter/results/evidence_verification.json](starter/results/evidence_verification.json) |
| 4 | Học viên đọc lại và chốt bộ câu hỏi, split | ✅ chốt ngày 2026-11-14 | `status: frozen` |
| 5 | Chunking A và B | ✅ | [starter/src/chunking.py](starter/src/chunking.py) |
| 6 | Embedding, lưu vào Chroma, kiểm tra nạp lại không trùng | ✅ A: 205 chunk, B: 139 chunk; 0 chunk bị cắt token; nạp lại không trùng; ~8 giây/index; chi phí 0 | [starter/results/index_stats.json](starter/results/index_stats.json) |
| 7 | Chốt tiêu chí chọn chiến lược trước khi xem test | ✅ Hit@3 dev → Hit@1 dev → ít chunk hơn | [starter/results/selection.json](starter/results/selection.json) |
| 8 | Chạy dev, rồi `select` để chọn chiến lược | ✅ dev Hit@3: A 7/15, B 11/15, C 12/15 → chọn C | `traces_dev.jsonl`, `metrics.json`, `selection.json` |
| 9 | Chạy test một lần với cấu hình đã cố định | ✅ test Hit@3: A 4/5, B 4/5, C 4/5; filter: A 0/2, B 0/2, C 2/2 | `traces_test.jsonl` |
| 10 | Chấm tay: coherence, metadata, grounding | ✅ (phương pháp chấm phải ghi trong báo cáo, xem mục Ghi chú) | `starter/results/audit_*.csv`, [audit_summary.json](starter/results/audit_summary.json) |
| 10b | **Cải tiến sau phân tích lỗi:** chiến lược D = C + tiêu đề ngữ cảnh + tách trang đáp án theo NGÀY (148 chunk). Được thiết kế **sau khi xem lỗi test t04/t05**. | ✅ dev D: Hit@1 7/15, Hit@3 12/15 (C: 4/15, 12/15). test2 Hit@1/Hit@3: A 0/3, B 1/2, C 2/2, D 2/2. test cũ (post-hoc) D = C | [benchmark/questions_test2.json](benchmark/questions_test2.json) (5 câu, chốt trước khi viết code D) |
| 11 | Experiment log, báo cáo, STUDENT.md, README | ✅ (còn điền link repo và commit chốt trong STUDENT.md) | [artifacts/experiment_log.csv](artifacts/experiment_log.csv), [report/individual/2A202603725_PhungThiNhai.md](report/individual/2A202603725_PhungThiNhai.md), [README.md](README.md) |

## Lệnh chạy (từ `starter/`, đã kích hoạt `.venv`)

```bash
python -m scripts.prepare_data          # manifest + kiểm tra evidence
python -m src.run index                 # chunk + embed + lưu + kiểm tra nạp lại
python -m src.run evaluate --split dev
python -m src.run select                # áp tiêu chí đã chốt lên kết quả dev
python -m src.run evaluate --split test # chỉ chạy được sau select
python -m src.run audit                 # tạo file CSV để chấm tay
```

## Ghi chú trung thực (đưa vào báo cáo)

- Code và bản nháp benchmark được viết với sự hỗ trợ của Claude Code. Học viên cần tự đọc lại và xác minh.
- Kiểm tra evidence tự động chỉ xác nhận câu trích có trên trang. Việc evidence có đủ để trả lời hay không do học viên xác nhận.
- Người chấm tay chính là tác giả, nên có nguy cơ thiên lệch.
- **Phương pháp chấm tay (bắt buộc ghi trong báo cáo):** nhãn coherence, metadata và grounding trong `audit_*.csv` do Claude (LLM) chấm theo thang 0–2 của GUIDE, sau khi đọc từng chunk. Mỗi nhãn có lý do riêng. Học viên đọc lại và xác nhận. Metadata được đối chiếu tự động (text chunk có trên trang, nhãn khớp trang) rồi mới gán Y/N.
