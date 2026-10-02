import os
import re
import pymupdf  # PyMuPDF

# --------------------------------------------------
# 【ユーザー入力】ファイル名の指定のみ
# --------------------------------------------------
input_pdf = input("PDFファイル名（パス）を入力してください: ").strip()

if not os.path.exists(input_pdf):
    print(f"エラー: 指定されたファイル '{input_pdf}' が見つかりません。")
    exit()

base, ext = os.path.splitext(input_pdf)
output_pdf = f"{base}_linked{ext}"

doc = pymupdf.open(input_pdf)

# ==================================================
# ★今回のPDF専用の設定
# ==================================================
toc_start_page = 51
toc_end_page = 102
page_offset = 6  # 本文116ページ ＝ 実際の122枚目 (122 - 116 = 6)

# 点々（様々なリーダー記号や空白）の後に数字で終わる行を検出する正規表現
regex_end_line = r"[\u00B7\.\uFF65\u2025\u2026\s\-\*・…]{2,}\s*（?(\d+)）?\s*\D*$"

print(f"【設定適用】目次範囲: {toc_start_page}P 〜 {toc_end_page}P / ページ補正: +{page_offset}")

# ==================================================
# 1. 物理的な「高さ（Y座標）」を基準に、左右のテキストを1行に並び替えて結合する
# ==================================================
all_pdf_lines = []
Y_TOLERANCE = 4  # 同じ行とみなす上下のズレの許容値

for page_num in range(toc_start_page, toc_end_page + 1):
    page = doc[page_num - 1]
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    spans = []
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    spans.append(span)
                    
    lines_dict = []
    for span in spans:
        y_center = (span["bbox"][1] + span["bbox"][3]) / 2
        
        placed = False
        for line in lines_dict:
            if abs(line["y_center"] - y_center) < Y_TOLERANCE:
                line["spans"].append(span)
                placed = True
                break
        if not placed:
            lines_dict.append({"y_center": y_center, "spans": [span]})
            
    lines_dict.sort(key=lambda x: x["y_center"])
    
    for line in lines_dict:
        line["spans"].sort(key=lambda x: x["bbox"][0])
        line_text = "".join([s["text"] for s in line["spans"]]).strip()
        
        x0 = min([s["bbox"][0] for s in line["spans"]])
        y0 = min([s["bbox"][1] for s in line["spans"]])
        x1 = max([s["bbox"][2] for s in line["spans"]])
        y1 = max([s["bbox"][3] for s in line["spans"]])
        
        all_pdf_lines.append({
            "page": page_num,
            "bbox": (x0, y0, x1, y1),
            "text": line_text
        })

# ==================================================
# 2. 全行をスキャンし、ガードを適用しながらリンク付与
# ==================================================
current_question = []

print(f"\n=== 内部リンク自動付与を開始 ===")

for line in all_pdf_lines:
    text = line["text"]
    
    # --------------------------------------------------
    # ★新機能：単なるページ番号表示（例: "- 95 -", "95", "— 95 —"）の行は完全に無視
    # --------------------------------------------------
    if re.match(r"^[\s\-\u2010-\u2015\u2212]*\d+[\s\-\u2010-\u2015\u2212]*$", text):
        continue  # この行の処理をスキップ（バッファにも入れない）
        
    # すべての正常な行を一旦バッファに溜める
    current_question.append(line)
    
    # 終端（点々＋ページ数）に達したかチェック
    match = re.search(regex_end_line, text)
    
    if match:
        combined_text = " ".join([item["text"] for item in current_question])
        
        original_dest_page = int(match.group(1))
        dest_page_index = (original_dest_page + page_offset) - 1
        
        link_page_num = current_question[0]["page"]
        page_obj = doc[link_page_num - 1]
        
        target_lines = [item for item in current_question if item["page"] == link_page_num]
        x0 = min([item["bbox"][0] for item in target_lines])
        y0 = min([item["bbox"][1] for item in target_lines])
        x1 = max([item["bbox"][2] for item in target_lines])
        y1 = max([item["bbox"][3] for item in target_lines])
        
        if 0 <= dest_page_index < len(doc):
            link_data = {
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(x0, y0, x1, y1),
                "page": dest_page_index
            }
            page_obj.insert_link(link_data)
            print(f"【成功】『{combined_text[:20]}...』 -> 目次 {link_page_num}P から 本文 {original_dest_page}P（PDFの {original_dest_page + page_offset} ページ目）へリンク")
        else:
            print(f"【警告】計算後のページ（{original_dest_page + page_offset}P）がPDFの総ページ数（{len(doc)}P）を超えているためスキップしました。")
        
        current_question = []

# 変更を保存
doc.save(output_pdf)
doc.close()
print(f"\nすべての処理が完了しました。保存先: {output_pdf}")
