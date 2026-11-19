#!/usr/bin/env python3
"""HexDiff - Comparateur hexadécimal de fichiers."""

import sys
import os
import argparse
import difflib
import html
import json


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def compute_diff(left: bytes, right: bytes) -> list:
    """
    Calculer la diff entre deux fichiers binaires.
    
    Approche hybride:
    - Comparaison LCS par blocs (taille adaptive)
    - Pour les blocs différents, LCS byte par byte pour extraire les sections communes
    """
    block_size = 64 if len(left) > 1_000_000 or len(right) > 1_000_000 else 16
    
    def chunkify(data: bytes) -> list:
        return [data[i:i+block_size] for i in range(0, len(data), block_size)]
    
    left_chunks = chunkify(left)
    right_chunks = chunkify(right)
    
    sm = difflib.SequenceMatcher(None, left_chunks, right_chunks, autojunk=False)
    
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            left_data = b"".join(left_chunks[i1:i2])
            right_data = b"".join(right_chunks[j1:j2])
            diffs.append(("equal", left_data, right_data, i1 * block_size, j1 * block_size))
        elif tag in ("replace", "delete", "insert"):
            left_data = b"".join(left_chunks[i1:i2]) if tag != "insert" else b""
            right_data = b"".join(right_chunks[j1:j2]) if tag != "delete" else b""
            byte_diffs = _byte_diff(left_data, right_data, i1 * block_size, j1 * block_size)
            diffs.extend(byte_diffs)
    
    return diffs


def _byte_diff(left: bytes, right: bytes, offset_l: int, offset_r: int) -> list:
    """
    LCS byte par byte. Retourne:
    (tag, left_bytes, right_bytes, offset_l, offset_r)
    """
    n = len(left)
    m = len(right)
    
    if n > 65536 or m > 65536:
        return [("replace", left, right, offset_l, offset_r)]
    if n == 0:
        return [("insert", b"", right, offset_l, offset_r)]
    if m == 0:
        return [("delete", left, b"", offset_l, offset_r)]
    
    # LCS table
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if left[i-1] == right[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    # Backtrack
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and left[i-1] == right[j-1]:
            ops.append(('equal', i-1, j-1))
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or dp[i][j-1] >= dp[i-1][j]):
            ops.append(('insert', i, j-1))
            j -= 1
        else:
            ops.append(('delete', i-1, j))
            i -= 1
    
    ops.reverse()
    
    # Grouper en ranges
    result = []
    current_tag = None
    left_start = right_start = 0
    
    for op, i, j in ops:
        if op == current_tag:
            continue
        if current_tag is not None:
            if current_tag == 'equal':
                result.append(('equal', left[left_start:i], right[right_start:j], offset_l + left_start, offset_r + right_start))
            elif current_tag == 'delete':
                result.append(('delete', left[left_start:i], b"", offset_l + left_start, offset_r))
            elif current_tag == 'insert':
                result.append(('insert', b"", right[right_start:j], offset_l + left_start, offset_r + right_start))
        current_tag = op
        if op == 'equal':
            left_start = i
            right_start = j
        elif op == 'delete':
            left_start = i
        elif op == 'insert':
            right_start = j
            left_start = i
    
    if current_tag == 'equal':
        result.append(('equal', left[left_start:], right[right_start:], offset_l + left_start, offset_r + right_start))
    elif current_tag == 'delete':
        result.append(('delete', left[left_start:], b"", offset_l + left_start, offset_r))
    elif current_tag == 'insert':
        result.append(('insert', b"", right[right_start:], offset_l + left_start, offset_r + right_start))
    
    return result


def group_diffs(diffs: list) -> list:
    """
    Fusionner les opérations non-equal adjacentes en un seul bloc
    ("change", octets_gauche, octets_droite, offset_gauche, offset_droite).
    """
    out = []
    pending = None
    for tag, ld, rd, ol, orr in diffs:
        if tag == "equal":
            if pending:
                out.append(tuple(pending))
                pending = None
            out.append((tag, ld, rd, ol, orr))
        elif pending is None:
            pending = ["change", ld, rd, ol, orr]
        else:
            pending[1] += ld
            pending[2] += rd
            pending[3] = min(pending[3], ol)
    if pending:
        out.append(tuple(pending))
    return out


def build_lines(diffs: list):
    """
    Aligner les deux fichiers sur une suite de "slots" (un slot = une case
    hex à gauche + la case en face à droite), puis découper en lignes de 16.
    Cellule: None (case vide) ou (octet, classe) avec classe in same/diff/del/add.
    Retourne (lignes, offsets):
      - lignes: liste de (cellules_gauche, cellules_droite)
      - offsets: pour chaque slot, (offset_gauche, offset_droite), None si case vide.
    Les offsets sont recomptés en cumulant les longueurs consommées.
    """
    slots = []
    offsets = []
    lpos = rpos = 0
    for tag, ld, rd, _, _ in group_diffs(diffs):
        if tag == "equal":
            for k, b in enumerate(ld):
                slots.append(((b, "same"), (b, "same")))
                offsets.append((lpos + k, rpos + k))
        else:
            # même longueur des deux côtés = modification (noir)
            modif = len(ld) == len(rd)
            for i in range(max(len(ld), len(rd))):
                left = (ld[i], "diff" if modif else "del") if i < len(ld) else None
                right = (rd[i], "diff" if modif else "add") if i < len(rd) else None
                slots.append((left, right))
                offsets.append((lpos + i if left else None, rpos + i if right else None))
        lpos += len(ld)
        rpos += len(rd)

    lines = []
    for i in range(0, len(slots), 16):
        chunk = slots[i:i + 16]
        lines.append(([s[0] for s in chunk], [s[1] for s in chunk]))
    return lines, offsets


def render_side(lines: list, side: int) -> str:
    """Colonne hex; chaque case porte data-i (n° de slot) pour la sélection."""
    out = []
    for r, pair in enumerate(lines):
        cells = []
        for k, c in enumerate(pair[side]):
            i = r * 16 + k
            if c is None:
                cells.append(f'<span class="gap" data-i="{i}">&middot;&middot;</span>')
            else:
                cells.append(f'<span class="{c[1]}" data-i="{i}">{c[0]:02X}</span>')
        out.append(" ".join(cells))
    return chr(10).join(out)


def render_ascii_side(lines: list, side: int) -> str:
    out = []
    for r, pair in enumerate(lines):
        chars = []
        for k, c in enumerate(pair[side]):
            i = r * 16 + k
            if c is None:
                chars.append(f'<span class="gap" data-i="{i}"> </span>')
            else:
                ch = chr(c[0]) if 0x20 <= c[0] <= 0x7E else chr(0xB7)
                chars.append(f'<span class="{c[1]}" data-i="{i}">{html.escape(ch)}</span>')
        out.append("".join(chars))
    return chr(10).join(out)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HexDiff</title>
<style>
:root {
  --bg: #ffffff; --fg: #1f2328; --same: #9aa0a6; --diff: #000000; --del: #d1242f; --add: #1a5fd0;
  --border: #d0d7de; --sel: #ffe9a8;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d1117; --fg: #e6edf3; --same: #6e7681; --diff: #ffffff; --del: #ff7b72; --add: #58a6ff;
    --border: #30363d; --sel: #5c4a00;
  }
}
body { background: var(--bg); color: var(--fg); margin: 0; padding: 16px;
       font-family: system-ui, sans-serif; }
h1 { font-size: 1.1rem; margin: 0 0 4px; }
.info { margin: 0 0 6px; font: 13px ui-monospace, Consolas, monospace; }
.legend { margin: 8px 0 16px; font-size: .85rem; display: flex; gap: 16px; flex-wrap: wrap; }
.cols { display: flex; gap: 24px; overflow-x: auto; }
.col { min-width: 0; }
.pair { display: flex; gap: 12px; }
.col h2 { font-size: .9rem; margin: 0 0 6px; font-weight: 600; }
pre { margin: 0; font: 14px/1.5 ui-monospace, Consolas, monospace; border: 1px solid var(--border);
      padding: 8px 12px; border-radius: 6px; }
[data-i] { cursor: pointer; border-radius: 2px; }
.sel { background: var(--sel); }
.same, .gap { color: var(--same); }
.diff { color: var(--diff); font-weight: 600; }
.del { color: var(--del); font-weight: 600; }
.add { color: var(--add); font-weight: 600; }
</style>
</head>
<body>
<h1>HexDiff</h1>
<div class="legend">
  <span><span class="same">XX</span> identique</span>
  <span><span class="diff">XX</span> modifié (même longueur)</span>
  <span><span class="del">XX</span> supprimé (gauche)</span>
  <span><span class="add">XX</span> ajouté (droite)</span>
  <span><span class="gap">&middot;&middot;</span> case vide</span>
</div>
<div class="cols">
  <div class="col"><h2>__LEFT__ (__LSIZE__ octets)</h2>
    <div class="info" id="off0">Offset : —</div>
    <div class="pair"><pre>__LBODY__</pre><pre>__LASCII__</pre></div></div>
  <div class="col"><h2>__RIGHT__ (__RSIZE__ octets)</h2>
    <div class="info" id="off1">Offset : —</div>
    <div class="pair"><pre>__RBODY__</pre><pre>__RASCII__</pre></div></div>
</div>
<script>
var OFF = __OFFSETS__;
var EMPTY = 'Offset : —';
var els = [];
document.querySelectorAll('[data-i]').forEach(function (x) {
  (els[+x.dataset.i] = els[+x.dataset.i] || []).push(x);
});
var selA = null, selB = null, dragging = false, moved = false, wasSingle = false;

function hex(o) { return '0x' + o.toString(16).toUpperCase().padStart(8, '0') + ' (' + o + ')'; }

function paint(on) {
  if (selA === null) return;
  var lo = Math.min(selA, selB), hi = Math.max(selA, selB);
  for (var i = lo; i <= hi; i++) {
    (els[i] || []).forEach(function (x) { x.classList.toggle('sel', on); });
  }
}

function info() {
  for (var side = 0; side < 2; side++) {
    var box = document.getElementById('off' + side);
    if (selA === null) { box.textContent = EMPTY; continue; }
    var lo = Math.min(selA, selB), hi = Math.max(selA, selB);
    var first = null, last = null, n = 0;
    for (var i = lo; i <= hi; i++) {
      var o = OFF[i][side];
      if (o === null) continue;
      if (first === null) first = o;
      last = o; n++;
    }
    if (n === 0) box.textContent = EMPTY;
    else if (n === 1) box.textContent = 'Offset : ' + hex(first);
    else box.textContent = 'Offset : ' + hex(first) + ' → ' + hex(last) + ' · ' + n + ' octets';
  }
}

document.querySelector('.cols').addEventListener('mousedown', function (e) {
  var t = e.target.closest('[data-i]');
  if (!t || e.button !== 0) return;
  e.preventDefault();
  var i = +t.dataset.i;
  wasSingle = selA !== null && selA === i && selB === i;
  paint(false);
  selA = selB = i;
  dragging = true; moved = false;
  paint(true); info();
});

document.addEventListener('mouseover', function (e) {
  if (!dragging) return;
  var t = e.target.closest && e.target.closest('[data-i]');
  if (!t) return;
  var i = +t.dataset.i;
  if (i === selB) return;
  paint(false);
  selB = i; moved = true;
  paint(true); info();
});

document.addEventListener('mouseup', function () {
  if (!dragging) return;
  dragging = false;
  if (!moved && wasSingle) { paint(false); selA = selB = null; info(); }
});
</script>
</body>
</html>
"""


def generate_html(left_path, right_path, diffs) -> str:
    lines, offsets = build_lines(diffs)
    return (HTML_TEMPLATE
            .replace("__LEFT__", html.escape(os.path.basename(left_path)))
            .replace("__RIGHT__", html.escape(os.path.basename(right_path)))
            .replace("__LSIZE__", f"{os.path.getsize(left_path):,}")
            .replace("__RSIZE__", f"{os.path.getsize(right_path):,}")
            .replace("__LBODY__", render_side(lines, 0))
            .replace("__LASCII__", render_ascii_side(lines, 0))
            .replace("__RBODY__", render_side(lines, 1))
            .replace("__RASCII__", render_ascii_side(lines, 1))
            .replace("__OFFSETS__", json.dumps(offsets)))


def main():
    parser = argparse.ArgumentParser(description="HexDiff - Comparateur hexadécimal")
    parser.add_argument("left", help="Premier fichier")
    parser.add_argument("right", help="Deuxième fichier")
    parser.add_argument("-o", "--output", default="hexdiff.html", help="Fichier HTML de sortie")

    args = parser.parse_args()
    
    for path in [args.left, args.right]:
        if not os.path.isfile(path):
            print(f"Erreur: '{path}' introuvable.", file=sys.stderr)
            sys.exit(1)
    
    print(f"Lecture {args.left}...")
    left = read_file(args.left)
    print(f"Lecture {args.right}...")
    right = read_file(args.right)
    
    print("Calcul de la diff...")
    diffs = compute_diff(left, right)

    print("Génération du HTML...")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(generate_html(args.left, args.right, diffs))
    print(f"Écrit dans: {args.output}")


if __name__ == "__main__":
    main()
