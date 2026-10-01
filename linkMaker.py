import os
import re
import pymupdf  # PyMuPDF

# --------------------------------------------------
# 【ユーザー入力】ファイル名の指定のみ
# --------------------------------------------------
input_pdf = input("PDFファイル名（パス）を入力してください: ").strip()

# ファイルの存在確認
if not os.path.exists(input_pdf):
    print(f"エラー: 指定されたファイル '{input_pdf}' が見つかりません。")
    exit()

# 出力ファイル名を自動生成 (例: input.pdf -> input_linked.pdf)
base, ext = os.path.splitext(input_pdf)
output_pdf = f"{base}_linked{ext}"

# PDFファイルを開く
doc = pymupdf.open(input_pdf)

# 判定用の正規表現
is_start_line = lambda text: text.strip().startswith("問")
is_end_line = lambda text: bool(re.search(r"[\u00B7\.\s]+\s*\d+\s*$", text.strip()))

# ==================================================
# ★ロジック改良：目次の最後のページ（toc_end_page）を「点々の連続」で自動判定
# ==================================================
toc_end_page = 1
toc_started = False

for page_num in range(1, len(doc) + 1):
    page = doc[page_num - 1]
    text_lines = page.get_text("text").split('\n')
    
    # 「·」や「.」が3回以上連続し、末尾が数字で終わる目次固有の行をカウント
    toc_line_count = 0
    for line in text_lines:
        if re.search(r"[\u00B7\.]{3,}\s*\d+\s*$", line.strip()):
            toc_line_count += 1
            
    # 1ページ内に目次特有の行が3行以上あれば、そこを目次ページとみなす
    if toc_line_count >= 3:
        toc_end_page = page_num
        toc_started = True
    else:
        # 目次エリアが一度始まってから、目次行がないページに到達したらそこで判定終了
        if toc_started:
            break

print(f"【自動認識】目次の最終ページを「 {toc_end_page} ページ 」と特定しました。")

# ==================================================
# 1. 特定された目次ページまでの行だけをフラットなリストに並べる
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
# 2. 全行をスキャンして塊を特定し、オフセットを考慮してリンクを付与
# ==================================================
current_question = []

print(f"\n=== 内部リンク自動付与（オフセット: +{toc_end_page}ページ）を開始 ===")

for line in all_pdf_lines:
    text = line["text"]
    bbox = line["bbox"]
    page_num = line["page"]
    
    if current_question or is_start_line(text):
        current_question.append({
            "text": text, 
            "bbox": bbox, 
            "page": page_num
        })
        
        # 終端（ページ数）に達したかチェック
        if is_end_line(text):
            # 全テキストを結合
            combined_text = " ".join([item["text"] for item in current_question])
            
            # 末尾の数字（テキストに記載されている本文のページ数）を抽出
            match = re.search(r"(\d+)\s*$", text.strip())
            if not match:
                current_question = []
                continue
                
            # 目次のテキストに書かれている元々のページ数
            original_dest_page = int(match.group(1))
            
            # 目次の最終ページ分を足して、実際のPDFの絶対ページ数を計算
            dest_page_index = (original_dest_page + toc_end_page) - 1
            
            # リンクを貼る対象のページ（目次が始まったページ）
            link_page_num = current_question[0]["page"]
            page_obj = doc[link_page_num - 1]
            
            # ユーザー様に修正いただいた正確な座標計算ロジック（bboxのインデックス指定）
            target_lines = [item for item in current_question if item["page"] == link_page_num]
            x0 = min([item["bbox"][0] for item in target_lines])
            y0 = min([item["bbox"][1] for item in target_lines])
            x1 = max([item["bbox"][2] for item in target_lines])
            y1 = max([item["bbox"][3] for item in target_lines])
            
            # 安全チェック: ジャンプ先ページがPDFの総ページ数を超えていないか
            if 0 <= dest_page_index < len(doc):
                # 内部リンクの定義
                link_data = {
                    "kind": pymupdf.LINK_GOTO,
                    "from": pymupdf.Rect(x0, y0, x1, y1),
                    "page": dest_page_index
                }
                # PDFにリンクを挿入
                page_obj.insert_link(link_data)
                print(f"【成功】『{combined_text[:15]}...』 -> 目次 {link_page_num}P から 本文 {original_dest_page}P（PDFの {original_dest_page + toc_end_page} ページ目）へリンク")
            else:
                print(f"【警告】計算後のページ（{original_dest_page + toc_end_page}P）がPDFの総ページ数（{len(doc)}P）を超えているためスキップしました。")
            
            # バッファをリセット
            current_question = []

# 変更を自動生成されたファイル名で保存
doc.save(output_pdf)
doc.close()
print(f"\nすべての処理が完了しました。保存先: {output_pdf}")
