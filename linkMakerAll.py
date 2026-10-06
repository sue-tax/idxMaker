import os
import re
import pymupdf  # PyMuPDF

# 全角数字を半角数字に変換するためのマッピングテーブル
ZEN_NUM = "０１２３４５６７８９"
HAN_NUM = "0123456789"
ZEN_TO_HAN = str.maketrans(ZEN_NUM, HAN_NUM)

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

# 終端行（目次行）の判定用正規表現：様々なリーダー記号、全角・半角数字に対応
regex_end_pattern = r"[\u00B7\.\uFF65\u2025\u2026\s\-\*・…]{2,}\s*（?([0-9０-９]+)）?\s*\D*$"
is_end_line = lambda text: bool(re.search(regex_end_pattern, text.strip()))

# ==================================================
# 1. 目次の最後のページ（toc_end_page）を自動判定
# ==================================================
toc_end_page = 1
toc_started = False

for page_num in range(1, len(doc) + 1):
    page = doc[page_num - 1]
    text_lines = page.get_text("text").split('\n')
    
    toc_line_count = 0
    for line in text_lines:
        if is_end_line(line):
            toc_line_count += 1
            
    if toc_line_count >= 3:
        toc_end_page = page_num
        toc_started = True
    else:
        if toc_started:
            break

print(f"【自動認識】目次の最終ページを「 {toc_end_page} ページ 」と特定しました。")

# ==================================================
# 💡 ★新機能：ページ下部のノンブルからページ補正値（オフセット）を完全自動解析
# ==================================================
page_offset = toc_end_page  # デフォルトのフォールバック値
detected = False

# 目次の終了直後から5ページ分をスキャンして、本文の「1ページ目」を探す
for check_page in range(toc_end_page + 1, min(toc_end_page + 6, len(doc) + 1)):
    page = doc[check_page - 1]
    page_height = page.rect.height
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            # ページ下部10%の領域（フッター部分）にあるテキストのみを対象にする
            if line["bbox"][1] > page_height * 0.9:
                line_text = "".join([span["text"] for span in line["spans"]]).strip()
                # 単一の数字（前後にハイフンや空白があっても可）を検出
                match_nombre = re.match(r"^[\s\-\u2010-\u2015\u2212]*([0-9０-９]+)[\s\-\u2010-\u2015\u2212]*$", line_text)
                
                if match_nombre:
                    # 全角数字を半角数字にクレンジング
                    nombre_str = match_nombre.group(1).translate(ZEN_TO_HAN)
                    nombre_val = int(nombre_str)
                    
                    # 補正値を割り出す (例: 物理6枚目のページ下部に 「1」 と書いてあれば 6 - 1 = +5)
                    page_offset = check_page - nombre_val
                    print(f"【自動検知】PDFの {check_page} 枚目の下部に 本文ページ数「{nombre_val}」を発見しました。")
                    detected = True
                    break
        if detected:
            break
    if detected:
        break

if not detected:
    print(f"【案内】ページ下部からノンブルを検知できなかったため、デフォルト値（目次の直後から本文）を採用します。")

print(f"【確定補正値】本文 1P ＝ PDFの {page_offset + 1} 枚目（オフセット: +{page_offset} ページ）\n")

# ==================================================
# 2. 目次ページまでの行だけをフラットなリストに並べる
# ==================================================
all_pdf_lines = []
for page_num in range(1, toc_end_page + 1):
    page = doc[page_num - 1]
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = "".join([span["text"] for span in line["spans"]]).strip()
            if line_text:
                all_pdf_lines.append({
                    "page": page_num,
                    "bbox": line["bbox"],
                    "text": line_text
                })

# ==================================================
# 3. 全行をスキャンして塊を特定し、自動リンクを付与
# ==================================================
current_question = []

print(f"=== 内部リンク自動付与を開始 ===")

for line in all_pdf_lines:
    text = line["text"]
    bbox = line["bbox"]
    page_num = line["page"]
    
    # ページ番号単体行（フッターなど）の誤判定をガード
    if re.match(r"^[\s\-\u2010-\u2015\u2212]*\d+[\s\-\u2010-\u2015\u2212]*$", text):
        continue  # 目次のページ番号はバッファに入れない
        
    current_question.append({
        "text": text, 
        "bbox": bbox, 
        "page": page_num
    })
    
    if is_end_line(text):
        combined_text = " ".join([item["text"] for item in current_question])
        
        match = re.search(regex_end_pattern, text.strip())
        if not match:
            current_question = []
            continue
            
        raw_page_str = match.group(1)
        clean_page_str = raw_page_str.translate(ZEN_TO_HAN)
        original_dest_page = int(clean_page_str)
        
        # 解析されたオフセットを適用
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
            print(f"【成功】『{combined_text[:15]}...』 -> 目次 {link_page_num}P から 本文 {original_dest_page}P（PDFの {original_dest_page + page_offset} ページ目）へリンク")
        else:
            print(f"【警告】計算後のページ（{original_dest_page + page_offset}P）がPDFの総ページ数（{len(doc)}P）を超えているためスキップしました。")
        
        current_question = []

# 変更を保存
doc.save(output_pdf)
doc.close()
print(f"\nすべての処理が完了しました。保存先: {output_pdf}")
