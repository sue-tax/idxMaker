'''
Created on 2026/09/27

@author: sue-t
'''

'''
TODO 目次設定の別保存も可

'''

import pymupdf
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextBoxHorizontal
import re
import os
import json
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from tkinter import ttk


__version__ = "0.10"

indexMaker = "idxMaker"

# デフォルトの設定ファイルの保存先
DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json") \
        if "__file__" in locals() else "config.json"

class ConvertKaisei(object):

    def __init__(self, input_file_name, start_page, end_page):
        '''
        Constructor
        '''
        self.input_file = input_file_name
        # self.output_text = '{}.txt'.format(output_file_name)
        self.border = 261
        # self.footer = 10
        # self.header = 800
        self.start_page = start_page # 開始ページ1スタート
        self.last_page = end_page  # 終了ページ

    def sorty_func(self, e):
        return - e.y1


    def readText(self):
        laparams = LAParams()               # パラメータインスタンス
        laparams.boxes_flow = None          # -1.0（水平位置のみが重要）から+1.0（垂直位置のみが重要）default 0.5
        laparams.word_margin = 0.2          # default 0.1
        laparams.char_margin = 2.0          # default 2.0
        laparams.line_margin = 0            # default 0.5
 
        # --- 1. ページ範囲のリストを作成 ---
        # ダイアログから取得した値を整数に変換（self.start_page, self.last_page に格納されていると仮定）
        try:
            start_p = int(self.start_page)
        except (AttributeError, ValueError):
            start_p = 1  # エラー時はデフォルト1ページ目から
            
        try:
            last_p = int(self.last_page)
        except (AttributeError, ValueError):
            last_p = 0   # エラー時はデフォルト最後まで
            
        # pdfminerは「0始まり」のインデックスを期待するため、1を引く
        # if start_p 4枚目なら start_idx 3
        start_idx = max(0, start_p - 1)
        
        # page_numbers引数に渡すページ番号のリストを組み立てる
        if last_p == 0:
            # 終了ページが0（最後まで）の場合は、いったんNone（全ページ対象）にしておき、
            # あとでループ内で判定するか、maxpages=0 のまま extract_pages に任せます。
            # ただし開始ページを反映させるため、巡回時にインデックスチェックを行います。
            page_numss = None
        else:
            # 終了ページが指定されている場合（例：開始2、終了5なら、インデックスは）
            last_idx = max(start_idx, last_p - 1)
            page_numss = list(range(start_idx, last_idx + 1))
        # ----------------------------------

        self.list_page = []
        
        # page_numbers 引数を追加して、必要なページだけを呼び出す
        for i, page_layout in enumerate(extract_pages(self.input_file,
                maxpages=0, laparams=laparams, page_numbers=page_numss)):
            
            # 終了ページが「最後まで(0)」で、開始ページが2番目以降の場合のスキップ処理
            # (page_numbers=Noneの時は全ページが返ってくるため、開始インデックス未満を飛ばす)
            if page_numss is None:
                if i < start_idx:
                    continue

            page_height = page_layout.height
            list_text = []
            list_textbox = []
            # list_rect = []
            # print(page_layout)
            for element in page_layout:
                # print(element)
                if isinstance(element, LTTextBoxHorizontal):
                    list_textbox.append(element)
            list_textbox.sort(key=self.sorty_func)
            # print(list_textbox)
            for textbox in list_textbox:
                # print(textbox)
                # print(textbox.x0, textbox.y1, page_layout.height)
                list_text.append( \
                        (textbox.get_text(), \
                        textbox.x0, page_height - textbox.y1 - 10 ))
                # print(textbox.get_text())
            self.list_page.append((i + 1, list_text))

        # for i, page in enumerate(self.list_page):
        #     # print(i)
        #     for text in page:
                # print(text)
                # for ch in text[0:5]:
                #     print(repr(ch))
            
    def pickupIndex(self, list_index):
        min_level = 99999
        list_toc = []
        before_level = 0
        dummy_point = pymupdf.Point(0, 0)
        # for num_page, page_data in enumerate(self.list_page):
        for page_data in self.list_page:
            for text in page_data[1]:
                bare_text = text[0].strip(" \n\r\t")
                for num_index, index in enumerate(list_index): 
                    m_index = index[1].match(bare_text)
                    if m_index:
                        # print(num_page, num_index, m_index, bare_text)
                        level = index[0]
                        # print(level, before_level)
                        if (level > before_level + 1):
                            while (level > before_level + 1):
                                toc = [ before_level+1, "(ダミー）", page_data[0],
                                        {
                                           "kind": pymupdf.LINK_GOTO,
                                           "to": dummy_point,
                                           "zoom": 0
                                        }]
                                list_toc.append(toc)
                                if (min_level > before_level+1):
                                    min_level = before_level+1
                                before_level += 1
                        point = pymupdf.Point(text[1], text[2])
                        toc = [ level, bare_text, page_data[0], \
                               {
                                   "kind": pymupdf.LINK_GOTO,
                                   "to": point,
                                   "zoom": 0
                                }]
                        # print(text)
                        # print(bare_text)
                        list_toc.append(toc)
                        before_level = level
                        if (min_level > level):
                            min_level = level
        return (list_toc, min_level)

    def writeIndex(self, toc):
        """PyMuPDFを使ってPDFに実際のしおりを書き込む"""
        if not toc:
            print("書き込むしおりがありません。")
            return False
        
        try:
            doc = pymupdf.open(self.input_file)
            # 既存のしおりを維持したい場合は doc.get_toc() と結合してください
            doc.set_toc(toc)
            # 元のファイルに上書き、または別名保存
            output_file = "output_" + os.path.basename(self.input_file)
            doc.save(output_file)
            doc.close()
            print(f"しおりの書き込みが完了しました: {output_file}")
            return True
        except Exception as e:
            print(f"しおり書き込みエラー: {e}")
            return False

# 日本語の選択肢を本物の正規表現に変換する辞書
CONVERT_MAP = {
    # --- 前（接頭辞） ---
    "全角括弧（": "（",
    "半角括弧(": "\\(",
    
    # --- 中（数字など） ---
    "半角数字123": "[0-9]+",
    "全角数字１２３": "[０-９]+",
    "漢数字一二三": "[一二三四五六七八九十百千万⼀⼆⼗]+",
    "片仮名アイウ": "[ア-ンヴヵヶ]",
    "平仮名あいう": "[あ-ん]",
    "半角片仮名ｱｲｳ": "[ｱ-ﾝ]",
    "ローマ数字ⅠⅡⅢ": "[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅫ]+",
    "ローマ数字ⅰⅱⅲ": "[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅻ]+",
    "半角大文字ABC": "[A-Z]",
    "半角小文字abc": "[a-z]",
    "全角大文字ＡＢＣ": "[Ａ-Ｚ]",
    "全角小文字ａｂｃ": "[ａ-ｚ]",
    "丸数字①②③": "[①-⑳]",
    "附則": "附[\\s\\u2003\\u200b]+則",
    
    # --- 後（接尾辞） ---
    "全角括弧）": "）",
    "半角括弧)": "\\)",
    "条..": "条\\S*"
}


def load_config_from_file(file_path):
    """指定されたパスからJSON設定ファイルを読み込む"""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("エラー", f"設定ファイルの読み込みに失敗しました:\n{e}")
    return None

def get_default_config():
    """初期値となるデフォルト設定を返す"""
    return {
        "pdf_path": "", "start_page": "1", "last_page": "0",
        "patterns": [
            {"level": "1", "prefix": "第", "middle": "半角数字123", "suffix": "章", "has_space": True},
            {"level": "2", "prefix": "", "middle": "半角数字123", "suffix": "節", "has_space": True},
            {"level": "3", "prefix": "半角括弧(", "middle": "半角数字123", "suffix": "半角括弧)", "has_space": False},
            {"level": "4", "prefix": "", "middle": "", "suffix": "", "has_space": False},
            {"level": "5", "prefix": "", "middle": "", "suffix": "", "has_space": False}
        ]
    }


def save_config(config_data, file_path):
    """指定されたファイルパスに設定をJSON形式で保存する"""
    try:
        # ディレクトリが存在しない場合は作成
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        print(f"設定を保存しました: {file_path}")
    except Exception as e:
        messagebox.showerror("エラー", f"設定の保存に失敗しました:\n{e}")


def show_input_dialog():
    """tkinterを使ってページ範囲と正規表現をまとめて入力するダイアログ"""
    root = tk.Tk()
    root.title("indexMaker version" + __version__)
    
    # 最初にデフォルトまたは直近の設定を読み込む
    current_config = load_config_from_file(DEFAULT_CONFIG_FILE) or get_default_config()
    
    # 現在読み込まれている設定ファイルのパスを保持する変数
    active_config_path = tk.StringVar(value=DEFAULT_CONFIG_FILE)
    
    # --- 設定ファイルの管理エリア ---
    config_frame = tk.LabelFrame(root, text="設定ファイルの管理", font=("", 9, "bold"))
    config_frame.grid(row=0, column=0, columnspan=5, sticky="ew", padx=10, pady=5)
    
    lbl_config_path = tk.Label(config_frame, text=os.path.basename(active_config_path.get()), fg="blue", wraplength=250)
    lbl_config_path.grid(row=0, column=2, padx=5, pady=5, sticky="w")
    
    # 【追加機能】別名で保存するボタンの処理
    def save_config_as():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON設定ファイル", "*.json")],
            initialfile=os.path.basename(active_config_path.get())
        )
        if file_path:
            active_config_path.set(file_path)
            lbl_config_path.config(text=os.path.basename(file_path))
            # 現在のUIの状態を入力データとしてまとめる
            config_to_save = gather_ui_data()
            save_config(config_to_save, file_path)
            messagebox.showinfo("完了", "設定を別名で保存しました。")

    def select_and_load_config():
        file_path = filedialog.askopenfilename(filetypes=[("JSON設定ファイル", "*.json")])
        if file_path:
            loaded = load_config_from_file(file_path)
            if loaded:
                active_config_path.set(file_path)
                lbl_config_path.config(text=os.path.basename(file_path))
                # （UIへの反映処理：以前のコードと同様）
                entry_pdf.delete(0, tk.END)
                entry_pdf.insert(0, loaded.get("pdf_path", ""))
                entry_start.delete(0, tk.END)
                entry_start.insert(0, loaded.get("start_page", "1"))
                entry_last.delete(0, tk.END)
                entry_last.insert(0, loaded.get("last_page", "0"))

                # --- [追加] 階層と正規表現（patterns）のUI復元処理 ---
                saved_patterns = loaded.get("patterns", [])
                
                for idx, row_entries in enumerate(pattern_rows):
                    # 保存されたデータがあれば取得、なければ空の初期値
                    if idx < len(saved_patterns):
                        p_data = saved_patterns[idx]
                    else:
                        p_data = {
                            "level": str(idx + 1), 
                            "prefix": "", 
                            "middle": "", 
                            "suffix": "", 
                            "has_space": False
                        }
                    
                    # 階層（Entry）の復元
                    row_entries["level"].delete(0, tk.END)
                    row_entries["level"].insert(0, p_data.get("level", str(idx + 1)))
                    
                    # 前・中・後（Combobox）の復元
                    row_entries["prefix"].set(p_data.get("prefix", ""))
                    row_entries["middle"].set(p_data.get("middle", ""))
                    row_entries["suffix"].set(p_data.get("suffix", ""))
                    
                    # 末尾に空白（チェックボックス）の復元
                    row_entries["has_space"].set(p_data.get("has_space", False))
                # -----------------------------------------------------
                
                messagebox.showinfo("完了", "設定ファイルを読み込みました。")

    tk.Button(config_frame, text="読み込む...", command=select_and_load_config) \
            .grid(row=0, column=0, padx=5, pady=5)
    tk.Button(config_frame, text="別名で保存...", command=save_config_as) \
            .grid(row=0, column=1, padx=5, pady=5)
    
    # --- PDFファイル入力 ---
    tk.Label(root, text="対象のPDFファイル:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    entry_pdf = tk.Entry(root, width=40)
    entry_pdf.insert(0, current_config.get("pdf_path", ""))
    entry_pdf.grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=5)
    
    def select_file():
        file_path = filedialog.askopenfilename(filetypes=[("PDFファイル", "*.pdf"), ("すべてのファイル", "*.*")])
        if file_path:
            entry_pdf.delete(0, tk.END)
            entry_pdf.insert(0, file_path)
    tk.Button(root, text="参照...", command=select_file).grid(row=1, column=4, padx=5, pady=5)
    
    # --- ページ範囲 ---
    tk.Label(root, text="開始ページ (1始まり):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    entry_start = tk.Entry(root, width=10)
    entry_start.insert(0, current_config.get("start_page", "1"))
    entry_start.grid(row=2, column=1, sticky="w", padx=5, pady=5)
    
    tk.Label(root, text="終了ページ (0で最後まで):").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    entry_last = tk.Entry(root, width=10)
    entry_last.insert(0, current_config.get("last_page", "0"))
    entry_last.grid(row=3, column=1, sticky="w", padx=5, pady=5)
    
    # --- 正規表現パターン入力エリア（グリッドヘッダー） ---
    current_row = 4
    tk.Label(root, text="しおりの階層と正規表現パターン設定", font=("", 9, "bold")).grid(row=current_row, column=0, columnspan=5, padx=5, pady=10)
    
    current_row += 1
    tk.Label(root, text="階層", width=5).grid(row=current_row, column=0, padx=2, pady=2)
    tk.Label(root, text="前（接頭辞）", width=12).grid(row=current_row, column=1, padx=2, pady=2)
    tk.Label(root, text="中（数字など）", width=18).grid(row=current_row, column=2, padx=2, pady=2)
    tk.Label(root, text="後（接尾辞）", width=12).grid(row=current_row, column=3, padx=2, pady=2)
    tk.Label(root, text="末尾に空白", width=10).grid(row=current_row, column=4, padx=2, pady=2)
    
    # ドロップダウンリストの選択肢
    prefix_options = ["", "第", "全角括弧（", "半角括弧("]
    middle_options = ["", "半角数字123", "全角数字１２３", "漢数字一二三", 
                      "片仮名アイウ", "平仮名あいう", "半角片仮名ｱｲｳ",
                      "ローマ数字ⅠⅡⅢ", "ローマ数字ⅰⅱⅲ", 
                      "半角大文字ABC", "半角小文字abc", "全角大文字ＡＢＣ", "全角小文字ａｂｃ",
                      "丸数字①②③", "附則"]
    suffix_options = ["", "編", "章", "節", "款", "目", "条..", "項", "全角括弧）", "半角括弧)"]
    
    # 各行のコンポーネントと独立したBool変数を保持するリスト
    pattern_rows = []
    saved_patterns = current_config.get("patterns", [])
    
    for i in range(10):
        current_row += 1
        
        # 過去の設定データがあれば読み込み、なければ初期値を設定
        p_data = saved_patterns[i] if i < len(saved_patterns) else {"level": str(i+1), "prefix": "", "middle": "", "suffix": "", "has_space": False}
        
        # 階層
        ent_level = tk.Entry(root, width=5, justify="center")
        ent_level.insert(0, p_data.get("level", str(i+1)))
        ent_level.grid(row=current_row, column=0, padx=2, pady=2)
        
        # 前（接頭辞）
        ent_prefix = ttk.Combobox(root, width=10, values=prefix_options)
        ent_prefix.insert(0, p_data.get("prefix", ""))
        ent_prefix.grid(row=current_row, column=1, padx=2, pady=2)
        
        # 中（数字など）
        ent_middle = ttk.Combobox(root, width=16, values=middle_options)
        ent_middle.insert(0, p_data.get("middle", ""))
        ent_middle.grid(row=current_row, column=2, padx=2, pady=2)
        
        # 後（接尾辞）
        ent_suffix = ttk.Combobox(root, width=12, values=suffix_options)
        ent_suffix.insert(0, p_data.get("suffix", ""))
        ent_suffix.grid(row=current_row, column=3, padx=2, pady=2)
        
        # 各行ごとに独立したチェックボックスの状態変数（BooleanVar）を作成
        var_space = tk.BooleanVar()
        var_space.set(p_data.get("has_space", False)) 
        
        chk_space = tk.Checkbutton(root, variable=var_space)
        chk_space.grid(row=current_row, column=4, padx=2, pady=2)
        
        # この行のコンポーネントへの参照をひとまとめにして保存
        pattern_rows.append({
            "level": ent_level,
            "prefix": ent_prefix,
            "middle": ent_middle,
            "suffix": ent_suffix,
            "has_space": var_space
        })
        
    result = {}

    
    def gather_ui_data():
        """UIの現在の入力内容を辞書オブジェクトにまとめる共通処理"""
        strip_chars = " \n\r\t"
        all_input_patterns = []
        for idx, row_entries in enumerate(pattern_rows, start=1):
            all_input_patterns.append({
                "level": row_entries["level"].get().strip(strip_chars),
                "prefix": row_entries["prefix"].get().strip(strip_chars),
                "middle": row_entries["middle"].get().strip(strip_chars),
                "suffix": row_entries["suffix"].get().strip(strip_chars),
                "has_space": row_entries["has_space"].get()
            })
        return {
            "pdf_path": entry_pdf.get().strip(strip_chars),
            "start_page": entry_start.get().strip(strip_chars),
            "last_page": entry_last.get().strip(strip_chars),
            "patterns": all_input_patterns
        }

    def on_submit():
        result["pdf_path"] = entry_pdf.get().strip()
        result["start_page"] = entry_start.get().strip()
        result["last_page"] = entry_last.get().strip()
        
        all_input_patterns = []
        parsed_patterns = []
        strip_chars = " \n\r\t"        
        for idx, row_entries in enumerate(pattern_rows, start=1):
            level_raw = row_entries["level"].get().strip(strip_chars)
            prefix_raw = row_entries["prefix"].get().strip(strip_chars)
            middle_raw = row_entries["middle"].get().strip(strip_chars)
            suffix_raw = row_entries["suffix"].get().strip(strip_chars)
            # 各行ごとにチェックされているか（True / False）を正確に取得
            has_space = row_entries["has_space"].get()
            
            # UI復元用（config.jsonにそのまま保存）
            pattern_item = {
                "level": level_raw, 
                "prefix": prefix_raw, 
                "middle": middle_raw, 
                "suffix": suffix_raw,
                "has_space": has_space
            }
            all_input_patterns.append(pattern_item)
            
            if middle_raw:
                try:
                    level_int = int(level_raw)
                except ValueError:
                    level_int = idx
                
                # 日本語表記から本物の正規表現コードへ置換
                prefix_regex = CONVERT_MAP.get(prefix_raw, prefix_raw)
                middle_regex = CONVERT_MAP.get(middle_raw, middle_raw)
                suffix_regex = CONVERT_MAP.get(suffix_raw, suffix_raw)
                
                # 行ごとのチェックが入っていれば、その行の末尾にのみ空白パターンを合体
                if has_space:
                    suffix_regex = f"{suffix_regex}[^\\S\\r\\n]+"
                
                active_item = {
                    "level": level_int,
                    "prefix": prefix_regex,
                    "middle": middle_regex,
                    "suffix": suffix_regex,
                    "full_regex": f"{prefix_regex}{middle_regex}{suffix_regex}"
                }
                parsed_patterns.append(active_item)
        
        parsed_patterns.sort(key=lambda x: x["level"])
        result["patterns"] = parsed_patterns
        
        # config.json 保存データの組み立て
        config_to_save = {
            "pdf_path": result["pdf_path"],
            "start_page": result["start_page"],
            "last_page": result["last_page"],
            "patterns": all_input_patterns
        }
        
        save_config(config_to_save, active_config_path.get())

        # save_config(config_to_save)
        root.destroy()
 
        
    def on_cancel():
        result.clear() 
        root.destroy()
        
    current_row += 1
    tk.Button(root, text="実行", command=on_submit, width=10).grid(row=current_row, column=1, pady=15)
    tk.Button(root, text="キャンセル", command=on_cancel, width=10).grid(row=current_row, column=2, pady=15)
    
    root.eval('tk::PlaceWindow . center')
    root.mainloop()
    
    return result

      
if __name__ == "__main__":
    # 1. ダイアログを表示して入力を取得
    user_inputs = show_input_dialog()
    # print(user_inputs)
    if (len(user_inputs) == 0):
        print("キャンセルされました")
        exit(0)

    list_index = []
    for row_entries in user_inputs.get("patterns"):
        # print(row_entries)
        # print(row_entries["level"])
        level = row_entries["level"]    #.get().strip()
        prefix = row_entries["prefix"] #.get().strip()
        middle = row_entries["middle"] #.get().strip()
        suffix = row_entries["suffix"] #.get().strip()
        
        # 「中（数字など）」が入力されている場合のみ有効なパターンとして扱う
        if middle:
            c_index = '^' + prefix + middle + suffix
            # print(c_index)
            p_index = re.compile(c_index)
            index = (int(level), p_index)
            list_index.append(index)

    cnv = ConvertKaisei(user_inputs.get("pdf_path"),
            int(user_inputs.get("start_page")),
            int(user_inputs.get("last_page")))
    cnv.readText()

    (list_toc, min_level) = cnv.pickupIndex(list_index)
    # print(list_toc)
    # print(min_level)
    
    toc = []
    for each in list_toc:
        print(each)
        print(each[0])
        print(each[1])
        print(each[2])
        print(each[3])
        each_toc = [ each[0] - min_level + 1, each[1], each[2], each[3] ]
        toc.append(each_toc)
    # print(toc)
    cnv.writeIndex(toc)
    del cnv
 