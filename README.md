PDF Heading & Title Extractor (Multilingual)

This tool extracts the title and headings (H1–H4) from PDF documents using visual, font-based, and multilingual heuristics. It is optimized to work offline, on CPU, within the constraints of the Adobe Hackathon 2025.

Features
1.Extracts:
   * Title (from first page or largest bold text)
   * Headings (H1, H2, H3, and now H4 levels)
2.Handles multi-line headings gracefully
3.Supports over 200 languages and scripts including Japanese, Hindi, Korean, and many more
4.Utilizes PyMuPDF for fast and reliable PDF text extraction
5.Employs heuristic scoring combining font size, weight, position, and style for robust heading detection
6.Fully offline, CPU-only — no internet or GPU required
7.Efficient performance: executes under 10 seconds for typical 50-page PDFs

Directory Structure 

ADOBE_HACK_ROUND1A/
├── input/
│   ├── file01.pdf
├── output/
│   ├── file01.json
├── main.py
├── dockerfile
├── requirements.txt
└── README.md


System workflow:

1.Build Docker Image:
docker build -t pdf-heading-extractor .

2.Run Extractor:
docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" pdf-heading-extractor

Processes all PDFs in the input folder and saves JSON outlines in output

Output Format :
{
  "title": "Document Title",
  "outline": [
    { "level": "H1", "text": "Main Section", "page": 1 },
    { "level": "H2", "text": "Subsection", "page": 3 },
    { "level": "H3", "text": "Detailed Topic", "page": 5 },
    { "level": "H4", "text": "Specific Point", "page": 7 }
  ]
}


Approach:

1.PDF Parsing: Uses PyMuPDF to extract text runs, fonts, sizes, positions.
2.Heading Detection: Applies heuristic scoring that factors font size, boldness, placement, and line breaks to identify headings and multi-line titles.
3.Multilingual Support: Fully Unicode-compliant, supports 200+ languages (including CJK and Indic scripts), ensuring accurate detection regardless of text script.
4.Hierarchy Construction: Groups extracted headings into Title, H1, H2, H3, and H4 levels based on relative font metrics and document structure cues.
5.Performance: Optimized for CPU-only processing, achieving full results within seconds on typical documents, compliant with hackathon constraints on speed and resource use.
6.Batch Mode: Supports processing multiple PDFs in the input folder in one run, outputs corresponding JSON in output.

Dependencies:
Python 3.9+
PyMuPDF (fitz)
Other dependencies listed in requirements.txt, installed during Docker build.

Notes:
1.No internet or GPU required; fully offline.
2.Robust to documents with non-uniform heading format styles.
3.Handles multi-line and multilingual headings reliably.
4.Output JSON strictly follows the required schema for easy integration.
