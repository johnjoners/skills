# Document extraction: local stack vs Unstructured

## What to check first

- pymupdf and pdfplumber for Python.
- The `pdftotext` (poppler) and `tesseract` (OCR) command-line tools.
- python-docx, openpyxl, and python-pptx for Office files, where installed.

For clean PDFs and Office files, the local tools are usually enough. Do not add a parser for them.

## When to use Unstructured

- Scanned or multi-column PDFs, forms, and tables that pdfplumber garbles. The hosted High-Res and VLM partitioning handles reading order and table-to-HTML better than tesseract plus pymupdf.
- Less common formats in one pass: .msg, .eml, .hwp, .epub, and old .doc or .ppt.
- Retrieval pipelines. It partitions, chunks (by title, by page, by similarity, or with contextual chunking), and embeds, keeping page and section metadata on each chunk.
- Scheduled syncs from Drive, SharePoint, OneDrive, Box, or Outlook into a vector database. This pays off for an ongoing sync, not for one-off files.

## Pricing (verify at unstructured.io/pricing before quoting)

- 10,000 free pages. The allowance is one-time, not monthly. No card is needed, and all features are included.
- Pay-as-you-go per page after that. Business plans are custom and add dedicated, VPC, or bare-metal hosting.
- Preview connectors need a request. They include Notion, GitHub, local filesystem, SFTP, and Chroma.
- Listed security terms: zero data retention, HIPAA, and SOC 2 Type 2.

## Open-source library

- `pip install "unstructured[all-docs]"`. Free and local.
- Heavy: it pulls in torch and detectron-style models.
- No VLM partitioning and no hosted enrichments. OCR still runs through tesseract.
- On clean files it isn't clearly better than the local stack.

## Placement

Add the hosted API as a fallback step in the PDF extraction path, used only when local output is empty or garbled. It does not warrant a standalone skill.
