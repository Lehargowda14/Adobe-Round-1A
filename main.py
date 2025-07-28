import os
import re
import json
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
from collections import Counter
from sklearn.cluster import KMeans

# -----------------------------
# Utility Functions
# -----------------------------
def clean_text(text):
    """Trim whitespace, keep Unicode characters."""
    if isinstance(text, str):
        return text.strip()
    return ""

def is_bold(span):
    font = span.get("font", "").lower()
    flags = span.get("flags", 0)
    return ("bold" in font) or (flags & 2 == 2)

def is_all_caps(text):
    if re.search(r'[A-Za-z]', text):
        return text.isupper() and len(text) > 2
    return False

def is_title_case(text):
    if re.search(r'[A-Za-z]', text):
        words = text.split()
        if not words:
            return False
        return sum(w[0].isupper() for w in words if w) / len(words) > 0.7
    return False

def is_centered(span, page_width, tol=0.15):
    x0, x1 = span["x0"], span["x1"]
    center = (x0 + x1) / 2
    return abs(center - page_width / 2) < tol * page_width

def line_length(span):
    return span["x1"] - span["x0"]

def is_numbered_list_item(text):
    return bool(re.match(r"^([0-9]+\.|[0-9]+\.[0-9]+|[a-zA-Z]\))\s", text.strip()))

def is_form_field(text):
    return bool(re.search(r"_{3,}", text))

def is_table_or_footer(text):
    return bool(re.match(r"^(page|copyright|confidential|prepared by|submitted by|table of contents|contents|contact|email|web|document)", text.strip(), re.I))

def is_multilingual(text):
    return bool(re.search(r'[\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]', text))  # Japanese, Chinese, Korean

# -----------------------------
# PDF Parsing
# -----------------------------
def extract_spans(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        blocks = page.get_text('dict')['blocks']
        for block in blocks:
            if 'lines' in block:
                for line in block['lines']:
                    if not line['spans']:
                        continue
                    sorted_spans = sorted(line['spans'], key=lambda s: s['bbox'][0])
                    merged_text = ' '.join(clean_text(span['text']) for span in sorted_spans if clean_text(span['text']))
                    if not merged_text:
                        continue
                    sizes = [span.get('size', 0) for span in sorted_spans]
                    fonts = [span.get('font', '') for span in sorted_spans]
                    flags = [span.get('flags', 0) for span in sorted_spans]
                    bolds = [is_bold(span) for span in sorted_spans]
                    max_size = max(sizes) if sizes else 0
                    any_bold = any(bolds)
                    main_font = max(set(fonts), key=fonts.count) if fonts else ''
                    first_span = sorted_spans[0]
                    last_span = sorted_spans[-1]
                    lines.append({
                        "text": merged_text,
                        "font": main_font,
                        "size": max_size,
                        "flags": flags[0] if flags else 0,
                        "bold": any_bold,
                        "page": page.number + 1,
                        "y0": first_span["bbox"][1],
                        "x0": first_span["bbox"][0],
                        "x1": last_span["bbox"][2],
                        "y1": first_span["bbox"][3],
                        "page_height": page.rect.height,
                        "page_width": page.rect.width
                    })
    doc.close()
    return pd.DataFrame(lines)

# -----------------------------
# Heading Detection Heuristics
# -----------------------------
DENYLIST = set([
    "page", "continued", "copyright", "prepared by", "submitted by", "table of contents",
    "contents", "contact", "email", "web", "document", "confidential"
])

def detect_body_size(df):
    if df.empty:
        return 0
    return df["size"].mode().iloc[0]

def heading_candidates(df, repeated_phrases, body_size):
    candidates = []
    for idx, row in df.iterrows():
        text = row["text"]
        if not text or len(text) < 3 or len(text) > 100:
            continue
        if text.lower() in DENYLIST or text in repeated_phrases:
            continue
        if is_table_or_footer(text) or is_form_field(text):
            continue
        if is_numbered_list_item(text) and row["size"] <= body_size * 1.18:
            continue
        if text.lower().startswith("page ") or text.lower() == "page" or re.fullmatch(r'^\d+$', text):
            continue
        if re.fullmatch(r"(january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2},? \d{4}", text, re.I):
            continue
        if re.search(r"\.\.\.+\s*\d+$", text):
            continue

        size_score = (row["size"] - body_size) / (body_size + 1e-3)
        bold_score = 1 if row["bold"] else 0
        caps_score = 1 if is_all_caps(text) else 0
        title_score = 1 if is_title_case(text) else 0
        center_score = 1 if is_centered(row, row["page_width"]) else 0
        short_line = 1 if line_length(row) < 0.7 * row["page_width"] else 0
        multilingual_score = 1 if is_multilingual(text) else 0

        score = (
            2*size_score +
            1.5*bold_score +
            1.2*caps_score +
            1.0*title_score +
            0.7*center_score +
            0.5*short_line +
            1.0*multilingual_score
        )
        if score > 1.5:
            candidates.append({**row, "score": score})
    return pd.DataFrame(candidates)

def assign_heading_levels(candidates, max_levels=4):
    if candidates.empty:
        candidates["level"] = []
        return candidates
    X = candidates[["size", "score", "bold"]].copy()
    X["bold"] = X["bold"].astype(int)
    n_clusters = min(max_levels, len(candidates["size"].unique()))
    km = KMeans(n_clusters=n_clusters, n_init="auto", random_state=42)
    clusters = km.fit_predict(X)
    candidates["cluster"] = clusters
    means = candidates.groupby("cluster")["size"].mean().sort_values(ascending=False)
    LEVELS = ["H1", "H2", "H3", "H4"]
    cluster_levels = {c: LEVELS[i] for i, c in enumerate(means.index)}
    candidates["level"] = candidates["cluster"].map(cluster_levels)

    h1_size = means.iloc[0]
    for idx, row in candidates.iterrows():
        if candidates.at[idx, "level"] == "H1":
            if not row["bold"] or row["size"] < h1_size or row["x0"] > 0.18 * row["page_width"]:
                candidates.at[idx, "level"] = "H2"

    h2_size = means.iloc[1] if len(means) > 1 else h1_size * 0.95
    for idx, row in candidates.iterrows():
        if candidates.at[idx, "level"] == "H2":
            if not (row["bold"] or is_title_case(row["text"])) or row["x0"] > 0.22 * row["page_width"] or row["size"] >= h1_size:
                candidates.at[idx, "level"] = "H3"
    return candidates

def merge_multiline_headings(candidates, y_gap_ratio=0.5):
    if candidates.empty:
        return candidates
    merged = []
    prev = None
    for idx, row in candidates.iterrows():
        if prev is None:
            prev = row.copy()
            continue
        y_gap = row["y0"] - prev["y1"]
        avg_size = (row["size"] + prev["size"]) / 2
        max_gap = avg_size * y_gap_ratio
        if (row["level"] == prev["level"] and row["size"] == prev["size"] and row["bold"] == prev["bold"] and row["page"] == prev["page"] and 0 <= y_gap < max_gap):
            prev["text"] = prev["text"].rstrip() + " " + row["text"].lstrip()
            prev["y1"] = row["y1"]
        else:
            merged.append(prev)
            prev = row.copy()
    if prev is not None:
        merged.append(prev)
    return pd.DataFrame(merged)

def extract_title(df, body_size):
    if df.empty:
        return ""
    page1 = df[df["page"] == 1]
    if page1.empty:
        return df.nlargest(1, "size").iloc[0]["text"]
    bold_large = page1[(page1["bold"]) & (page1["size"] >= page1["size"].quantile(0.85))]
    if not bold_large.empty:
        return bold_large.iloc[0]["text"]
    return page1.nlargest(1, "size").iloc[0]["text"]

def process_pdf(pdf_path, output_json):
    spans = extract_spans(pdf_path)
    if spans.empty:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump({"title": "", "outline": []}, f, indent=2, ensure_ascii=False)
        return
    spans = spans[spans["text"].map(len) > 0]
    text_counts = spans["text"].value_counts()
    repeated = set(text_counts[text_counts > max(2, spans["page"].nunique() // 2)].index)
    body_size = detect_body_size(spans)
    candidates = heading_candidates(spans, repeated, body_size)
    if not candidates.empty:
        candidates = assign_heading_levels(candidates, max_levels=4)
        candidates = candidates.drop_duplicates(subset=["text", "level", "page"], keep="first")
        candidates = candidates.sort_values(["page", "y0"]).reset_index(drop=True)
        candidates = merge_multiline_headings(candidates)
        outline = [
            {"level": r["level"], "text": r["text"], "page": int(r["page"])}
            for _, r in candidates.iterrows()
        ]
        title = extract_title(spans, body_size)
    else:
        outline = []
        title = extract_title(spans, body_size)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"title": title, "outline": outline}, f, indent=2, ensure_ascii=False)

def main():
    input_dir = "input"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    for fname in os.listdir(input_dir):
        if fname.lower().endswith(".pdf"):
            process_pdf(
                os.path.join(input_dir, fname),
                os.path.join(output_dir, fname.replace(".pdf", ".json"))
            )
            print(f"Processed: {fname}")

if __name__ == "__main__":
    main()
