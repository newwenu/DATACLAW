#!/usr/bin/env bash
# pdf-translate helper — find pdf2zh_next and translate a PDF
# Usage: translate_pdf.sh <input.pdf> [lang_out] [pages] [output_dir]
# Defaults: lang_out=zh-CN, pages=all, output_dir=current directory
set -euo pipefail

INPUT="${1:-}"
LANG_OUT="${2:-zh-CN}"
PAGES="${3:-}"
OUTPUT="${4:-.}"

if [ -z "$INPUT" ]; then
    echo "Usage: translate_pdf.sh <input.pdf> [lang_out] [pages] [output_dir]"
    echo "Example: translate_pdf.sh paper.pdf zh-CN 1-10 ./output"
    exit 1
fi

if [ ! -f "$INPUT" ]; then
    echo "Error: file not found: $INPUT"
    exit 1
fi

# Find pdf2zh_next binary
PDF2ZH=""
for candidate in \
    "pdf2zh_next" \
    "$HOME/Library/Application Support/uv/tools/pdf2zh-next/bin/pdf2zh_next" \
    "$HOME/.local/bin/pdf2zh_next" \
    "$(which pdf2zh_next 2>/dev/null)"; do
    if command -v "$candidate" &>/dev/null; then
        PDF2ZH="$candidate"
        break
    fi
done

if [ -z "$PDF2ZH" ]; then
    echo "pdf2zh_next not found. Install with:"
    echo "  pip install uv && uv tool install --python 3.12 pdf2zh-next"
    exit 1
fi

mkdir -p "$OUTPUT"

ARGS=("$INPUT" "--lang-out" "$LANG_OUT" "--output" "$OUTPUT")
if [ -n "$PAGES" ]; then
    ARGS+=(--pages "$PAGES")
fi

echo "Tool:      $PDF2ZH"
echo "Input:     $INPUT"
echo "Lang out:  $LANG_OUT"
echo "Output:    $OUTPUT"
echo "---"

"$PDF2ZH" "${ARGS[@]}"
