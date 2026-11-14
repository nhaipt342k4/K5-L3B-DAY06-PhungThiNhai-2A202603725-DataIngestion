# Báo cáo cá nhân — Day 6

**Phùng Thị Nhài · 2A202603725 · L3B** · Ngày chạy: 2026-11-14

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Tài liệu: *Xây nền ngữ pháp trong 30 ngày* (Datio English, 30-Day Grammar Foundation Workbook, tiếng Việt kèm ví dụ tiếng Anh), tải ngày 2026-11-14 từ thư viện tự học ieltsdatio.edu.vn.
  - Quyền sử dụng: tài liệu phát miễn phí nhưng không ghi giấy phép tái phân phối. Vì vậy em chỉ dùng cho bài tập, xử lý hoàn toàn local, không gửi tới API nào và **không commit PDF**; README ghi cách tải lại.
  - Số trang: PDF có 47 trang vật lý, em tính **40 trang nội dung** (trang 5–44, gồm 24 trang bài học, 4 ôn tập, 4 Mini Test, Error Clinic, Final Check, 5 trang đáp án và cheat sheet).
  - Loại 7 trang: bìa (1), quảng cáo (2, 45, 46, 47), hướng dẫn cách học (3), bản đồ 30 ngày tương đương mục lục (4).
  - Tổng 87.567 ký tự sau chuẩn hóa. Quy ước: `page` là số trang PDF vật lý; số in ở chân trang nhỏ hơn 1 đơn vị và được lưu riêng ở `printed_page`. Xem [data/manifest.json](../../data/manifest.json).
- **Chuẩn hóa, lỗi và giới hạn:**
  - Đọc từng trang bằng pypdf 6.21.4, chuẩn hóa NFKC (vừa ghép dấu tiếng Việt, vừa tách chữ ghép "ﬁ"), gộp khoảng trắng nhưng giữ xuống dòng.
  - Do layout, pypdf trả tiêu đề trang ở **cuối** text, sau dòng footer quảng cáo. Em bỏ footer và đưa các dòng tiêu đề lên đầu trang.
  - Trang 42 có footer dính chung dòng với nội dung; lần đầu regex bỏ sót, em đã phát hiện và sửa.
  - Log: 0 trang rỗng, 0 trang lỗi.
  - pypdf báo "Ignoring wrong pointing object" (bảng tham chiếu nội bộ của PDF bị lệch, text không bị ảnh hưởng); em đặt logger pypdf ở mức ERROR.
  - Giới hạn còn lại: các dòng bị ngắt giữa câu do layout 2 cột chỉ được nối lại khi chia chunk theo đoạn; một số chỗ mất khoảng trắng (ví dụ "2To be"); không cần OCR.
- **Embedding, vector store, metric, lệnh chạy và chi phí:**
  - Embedding: `intfloat/multilingual-e5-small` qua sentence-transformers 6.3.0 (torch 2.15.0 CPU), chạy local, 384 chiều, tối đa 512 token. Document được thêm tiền tố `passage: `, query thêm `query: `, vector chuẩn hóa L2.
  - Giảng viên gợi ý `all-MiniLM-L6-v2`, nhưng model đó chỉ hỗ trợ tiếng Anh nên em chọn model đa ngữ.
  - Không chunk nào vượt 512 token (lớn nhất 334).
  - Vector store: Chroma 1.5.9, `PersistentClient` tại `starter/chroma_db/`, cosine, HNSW (tìm kiếm xấp xỉ), filter metadata chạy bên trong Chroma.
  - Em không dùng pgvector vì máy không có Docker.
  - Python 3.12.10. Chi phí **0** (không dùng dịch vụ trả phí). Lệnh chạy xem [README](../../README.md).
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - Bắt buộc: `document_id`, `source`, `page`; thêm `printed_page`.
  - Trường lọc: `page_type` (lesson / review / mini_test / error_clinic / final_test / answer_key / appendix), `week` (1–4), `day_start`/`day_end` (int), `title`.
  - Mọi giá trị được trích bằng regex từ **nhãn in trên trang** ("NGÀY 08 • TUẦN 2", "Mini Test tuần 2", "Đáp án & giải thích ngày 14-20"), không có giá trị nào tự đoán. Trang đáp án và trang 37–38 không in tuần nên không có `week`.
  - Lý do chọn: cùng một quy tắc lặp lại ở trang bài học, trang ôn tập và trang đáp án; bảng "HỌC LẠI" của 4 tuần gần như giống nhau, chỉ khác số ngày. Vì vậy cần lọc theo tuần và loại trang.

## Cấu hình và benchmark

- **A / B / C:** Cả ba dùng cùng corpus, cùng model và cùng 20 câu hỏi; top-k = 3.
  - **A:** `fixed_size`, cửa sổ 500 ký tự, overlap 50, không lọc. 205 chunk.
  - **B:** `by_paragraph`, tách tại heading của workbook (HIỂU BẢN CHẤT, QUY TẮC, LỖI DỄ MẮC, NGÀY xx…), nối lại các dòng bị ngắt, gom khối tới 800 ký tự, khối quá dài thì tách theo câu. Không lọc. 139 chunk.
  - **C:** dùng **chung index với B**, chỉ thêm filter khi câu hỏi có `filter`. Câu không có filter thì C chạy như B.
  - Vì vậy **A–B chỉ khác cách chunk, B–C chỉ khác bước lọc**.
- **20 câu hỏi:**
  - 15 dev / 5 test, chia và chốt (`status: frozen`) trước khi chạy retrieval. Các câu gồm: trực tiếp, diễn đạt lại, điều kiện/ngoại lệ và 5 câu có filter (3 dev: q11, q12, q13; 2 test: t04, t05).
  - Tập test được chọn từ các chủ điểm không trùng với dev. Rủi ro rò rỉ còn lại: cùng một quy tắc in lại ở nhiều trang; mọi trang hợp lệ được ghi trong `gold_pages`.
  - Kiểm chứng evidence: script `prepare_data` so khớp `evidence_quote` (sau NFKC, gộp khoảng trắng, không phân biệt hoa thường) với **mọi** trang. 20/20 câu khớp; hai câu có thêm trang hợp lệ (q12 → trang 42, t05 → trang 41) đã được bổ sung vào `gold_pages`.
  - Filter là dữ liệu đầu vào giả định do ngữ cảnh cung cấp trước khi truy xuất (ví dụ người dùng đang tra đáp án → `page_type=answer_key`), không chứa đáp án hay trang gold.
- **Tiêu chí chọn chiến lược, chốt trước khi chạy dev và test** ([selection.json](../../starter/results/selection.json)):
  1. Evidence Hit@3 trên dev cao nhất.
  2. Nếu bằng: Hit@1 trên dev cao nhất.
  3. Nếu vẫn bằng: ít chunk hơn.

  Lệnh `select` áp tiêu chí này, kết quả: C (12/15) > B (11/15) > A (7/15) → **chọn C**.

## Kết quả

Hit = chunk thuộc nguồn gold, nằm ở một trang trong `gold_pages` và chứa **đủ** `evidence_quote`.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 3/15 | 7/15 | 205 | embed 8,3 s (CPU) | 0 |
| B | dev | 4/15 | 11/15 | 139 | embed 7,9 s | 0 |
| C | dev | 4/15 | **12/15** | 139 (chung với B) | như B | 0 |
| A | test | 2/5 | 4/5 | 205 | | 0 |
| B | test | 3/5 | 4/5 | 139 | | 0 |
| C | test | 3/5 | 4/5 | 139 | | 0 |

Đúng trang gold trong top-3 (không xét evidence): dev A/B/C đều 14/15; test A 4/5, B 4/5, C 5/5.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,0 (n=10) | 15/15 | dev 1/3 · test 0/2 | 1 / 1 / 3 → 1,4 |
| B | 1,9 (n=10) | 15/15 | dev 1/3 · test 0/2 | 1 / 1 / 3 → 1,4 |
| C | 1,9 (n=10, cùng chunk với B) | 15/15 | dev 3/3 · test 2/2 | 1 / 0 / 4 → 1,6 |

Ở A và B, "filter tuân thủ" chỉ đo xem top-3 có tình cờ nằm trong phạm vi filter hay không; A và B không áp dụng filter.

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- Trace top-3 đầy đủ (câu hỏi, chunk ID, text, score, metadata, cờ hit): `starter/results/traces_dev.jsonl`, `traces_test.jsonl`.
- Nhãn: `audit_coherence.csv`, `audit_metadata.csv`, `audit_grounding.csv`; tổng hợp trong `audit_summary.json`.
- Mẫu coherence được cố định trước khi xem điểm: 10 trang nội dung đầu tiên theo thứ tự (trang 5–14), vị trí = 40 ký tự ở **giữa** text đã chuẩn hóa của trang. Với mỗi chiến lược, em chấm chunk chứa vị trí đó.
- Metadata: 5 câu test × top-3 × 3 chiến lược = 45 bản ghi.
- Grounding: 5 câu test × 3 chiến lược, chấm dựa trên cả top-3.

**Phương pháp chấm tay (khai báo):**
- Nhãn coherence, metadata và grounding do Claude (LLM, qua Claude Code) chấm theo đúng thang 0–2 của GUIDE sau khi đọc từng chunk; mỗi nhãn kèm một lý do. Em đã đọc lại toàn bộ nhãn và lý do, và đồng ý.
- Metadata được đối chiếu tự động trước (text của chunk có nằm trên trang đó không, `page_type`/`week`/`day` có khớp nhãn in trên trang không), sau đó mới gán Y/N.
- Rủi ro thiên lệch: người chấm cũng là bên thiết kế pipeline, và không có người chấm độc lập thứ hai.

## Phân tích và kết luận

- **Retrieval accuracy:**
  - Trên dev, B hơn A rõ rệt (11/15 so với 7/15), và C hơn B một câu (12/15).
  - Hit@1 thấp ở cả ba (3–4/15). Điểm cosine của top-3 rất sát nhau (khoảng 0,85–0,91) vì 24 trang bài học dùng chung một khuôn.
  - Trên test, cả ba đều 4/5. Với N=5, chênh 1 câu bằng 20 điểm phần trăm, nên em không kết luận chiến lược nào vượt trội trên test.
- **A–B, khác cách chunk:**
  - Tới 14/15 câu dev, cả A và B đều tìm đúng **trang** trong top-3. A thua vì cửa sổ 500 ký tự cắt ngang evidence hoặc lấy nhầm đoạn khác của cùng trang.
  - Ví dụ: q04 (vị trí trạng từ tần suất), chunk A ở trang 16 chỉ chứa một nửa câu evidence; q09 và q14, A tìm đúng trang 34/24 nhưng sai đoạn, còn B trúng.
  - Coherence phản ánh cùng hiện tượng: cả 10 chunk A đều mở đầu hoặc kết thúc giữa chữ ("tiː.tʃər/", "LUYỆN T") nên chỉ được 1/2. B được 2/2 ở 9/10 vị trí. Vị trí còn lại là trang 12 (Mini Test), bị cắt cứng ở "17." do giới hạn 800 ký tự.
  - Về tài nguyên, B dùng ít chunk hơn (139 so với 205) và ít ký tự lưu hơn (87.468 so với 95.817 vì không có overlap).
- **B–C, chỉ khác filter:**
  - Filter giúp ở câu có phạm vi rõ. q13 (Mini Test tuần 1 câu 15): B không có hit, C lọc `week=1, page_type=mini_test` và kéo được trang 12 vào top-3.
  - t05 (tuần 2, sai câu 7-8): A và B đều có câu trả lời ở top-1 nhưng top-2/3 lẫn bảng HỌC LẠI của tuần 3 và 4 với quy tắc khác, dễ gây trả lời sai. C cho cả top-3 thuộc tuần 2, kèm trang 20 ghi rõ "Mini Test tuần 2". Grounding vì thế tăng từ 1 lên 2.
  - Filter tuân thủ: C 3/3 (dev) và 2/2 (test); B 1/3 và 0/2.
  - Hạn chế: trang đáp án không in tuần, nên filter `week=3` ở q12 loại luôn trang đáp án 42, dù trang đó là một nguồn hợp lệ.
- **Metadata usefulness:** 45/45 bản ghi có `source`/`page` đúng và `page_type`/`week`/`day` khớp nhãn in trên trang.
  - Trường hữu ích nhất là `page_type` (tách câu tra đáp án khỏi trang đề) và `week` (tách 4 bảng HỌC LẠI gần như giống nhau).
  - `page` + `printed_page` giúp truy vết: người dùng nhìn số in trên giấy vẫn tìm đúng trang PDF.
  - Hạn chế: `page_type=answer_key` chỉ thu hẹp về 5 trang đáp án, chưa đủ để chọn đúng ngày (xem lỗi 1).
- **Grounding:** đây là đánh giá độ đủ của bằng chứng truy xuất, không phải độ chính xác câu trả lời của LLM.
  - t01, t02, t03 được 2 ở cả ba chiến lược. t04 được 0 ở cả ba.
  - Riêng t05: A và B được 1 vì chunk không ghi "tuần 2" và có quy tắc nhiễu; C được 2.
- **Hai ví dụ sai:**
  1. **t04** "Đáp án câu 8 của Error Clinic ngày 29?", gold trang 43.
     - A và B trả về trang **37** (trang đề Error Clinic, chỉ có câu sai). Câu hỏi giống đề hơn giống đáp án.
     - C lọc `answer_key` và trả về đúng trang 43, nhưng là chunk `p43:p00` (đáp án ngày 28). Đoạn "NGÀY 29: … 8 I went to bed because I was tired" nằm ở `p43:p01`, bị gộp chung với giải thích ngày 28 và đáp án ngày 30.
     - Dev có lỗi cùng loại ở **q11** (đáp án Mini Test tuần 2 câu 6, gold trang 41): cả ba trả về trang đáp án 43/42/40, sai trang.
  2. **n02/n03** (tập test2), "Có được viết 'the my book' không?", gold trang 9.
     - B, C và D đều về đúng trang 9 nhưng lấy chunk LUYỆN TẬP ("Chọn đúng: This is my/the my book"), thay vì chunk LỖI DỄ MẮC ("the my book → my book. Không đặt the trước tính từ sở hữu").
     - Câu hỏi diễn đạt giống bài tập nên khớp chunk bài tập hơn chunk quy tắc.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - Chọn **C** theo tiêu chí đã chốt. Chi phí giống B (cùng index), coherence cao, và chỉ C giữ đúng phạm vi tuần/loại trang khi người dùng cung cấp ngữ cảnh.
  - Đánh đổi:
    - Filter cứng có thể loại nguồn hợp lệ không có trường đó (trang đáp án không có `week`).
    - Filter phụ thuộc vào việc ngữ cảnh cung cấp đúng giá trị; trong bài này giá trị filter được cho sẵn trong benchmark.
    - Chunk theo heading phụ thuộc vào bố cục riêng của workbook này (danh sách heading được viết tay).
  - Điều kiện áp dụng: tài liệu có khuôn trang lặp lại và nhãn phạm vi in sẵn. Không suy rộng ra corpus khác.

### Cải tiến sau phân tích lỗi (post-hoc, chiến lược D)

- Sau khi xem lỗi t04/t05, em thiết kế **D** = C + tiêu đề ngữ cảnh ở đầu mỗi chunk + tách trang đáp án theo từng khối NGÀY.
  - Tiêu đề lấy từ metadata, ví dụ `[Tuần 2 | Ngày 14 | Ôn tập]`.
  - Mỗi khối NGÀY trên trang đáp án được gắn `day_start`/`day_end` riêng.
  - D có 148 chunk, embed 8,9 s.
- Vì D được thiết kế **sau khi đã xem test**, em không dùng test gốc để đánh giá nó. Thay vào đó em viết **test2**: 5 câu mới, chủ điểm không trùng, 2 câu có filter, chốt **trước khi viết code D** ([questions_test2.json](../../benchmark/questions_test2.json)). D chạy trên test gốc chỉ để tham khảo và được lưu với tag `__posthoc`.

| Strategy | dev Hit@1 | dev Hit@3 | test2 Hit@1 | test2 Hit@3 | test2 filter | test gốc (post-hoc) Hit@1 / Hit@3 |
|---|---|---|---|---|---|---|
| A | 3/15 | 7/15 | 0/5 | 3/5 | 0/2 | – |
| B | 4/15 | 11/15 | 1/5 | 2/5 | 0/2 | – |
| C | 4/15 | 12/15 | 2/5 | 2/5 | 2/2 | – |
| D | **7/15** | 12/15 | 2/5 | 2/5 | 2/2 | 3/5 / 4/5 |

- **Nhận xét:**
  - Tiêu đề ngữ cảnh cải thiện Hit@1 trên dev (q03, q05, q09, q10 lên top-1; q10 có hit lần đầu). Nhưng nó làm q06 mất hit@3 và q01 rơi khỏi top-1: tiêu đề giống nhau khiến các chunk cùng bài trông giống nhau hơn.
  - Trên test2, D **bằng** C. Trên test gốc chạy post-hoc, t04 **vẫn trượt**: top-3 của D đều ở trang 43 nhưng là khối ngày 28, ngày 30 và phần đầu trang. n04 (đáp án ngày 18) cũng trượt.
  - Như vậy embedding dense không phân biệt được các con số như "ngày 18" hay "ngày 29", kể cả khi đã có tiêu đề.
  - Không đủ bằng chứng để thay C bằng D.
- **Hạn chế:**
  - Benchmark nhỏ (15/5/5 câu) và do một người viết (có AI hỗ trợ soạn nháp).
  - Câu hỏi có thể vô tình dùng từ gần với văn bản gốc.
  - Thời gian chỉ đo bước embed trên CPU của một máy, không lặp lại nhiều lần.
  - HNSW là tìm kiếm xấp xỉ, nhưng với vài trăm chunk thì sai lệch không đáng kể.
  - Nhãn chấm tay do LLM chấm nháp, em duyệt lại; không có người chấm thứ hai.
  - Phần cải tiến D là post-hoc; test2 chỉ có 5 câu.
- **Nếu làm lại hoặc mở rộng, em sẽ cải tiến:**
  1. Tự trích filter từ câu hỏi bằng regex cho "tuần X", "ngày Y", "đáp án". Lọc theo khoảng `day_start ≤ Y ≤ day_end`, và nới lỏng filter khi lọc cứng không trả kết quả.
  2. Kết hợp BM25 với dense retrieval để khớp chính xác từ khóa và con số; chọn trọng số trên dev và báo cả những câu bị xấu đi.
  3. Gắn `week` cho từng khối trên trang đáp án dựa vào dòng "MINI TEST TUẦN x".
  4. Viết thêm câu hỏi (≥ 50) và nhờ người chấm thứ hai để đo độ đồng thuận giữa hai người chấm.

**Công cụ AI:** Claude Code (Claude Opus 5.5) hỗ trợ viết code pipeline, soạn nháp benchmark và chấm nháp nhãn. Em đã tự xác nhận:
- bộ câu hỏi, cách chia dev/test và test2;
- tiêu chí chọn chiến lược trước khi chạy;
- toàn bộ nhãn chấm tay.

Em tự chạy các lệnh pipeline; mọi số liệu trong báo cáo lấy từ `metrics.json`, `index_stats.json` và `audit_summary.json`.
