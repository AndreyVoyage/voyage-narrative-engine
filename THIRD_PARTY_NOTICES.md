# THIRD_PARTY_NOTICES.md — Voyage Narrative Engine

This file lists third-party software components distributed with or
relied upon by the Voyage Narrative Engine Character Aside module.

---

## SQLite 3.45.3 — Public Domain

**Component:** SQLite 3.45.3 amalgamation (statically linked into `_sqlite3.pyd`)

**License:** Public Domain

The author disclaims copyright to this source code. In place of a legal
notice, here is a blessing:

  May you do good and not evil.
  May you find forgiveness for yourself and forgive others.
  May you share freely, never taking more than you give.

**Source:** https://sqlite.org/download.html
**SHA-256 (amalgamation archive):** `ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651`

**Local notice:** `novel/game/python-packages/NOTICE.txt`

---

## CPython 3.12.7 — PSF License

**Component:** CPython 3.12.7 `_sqlite3` native extension wrapper and `sqlite3`
pure-Python package.

**License:** Python Software Foundation License Version 2
(https://docs.python.org/3.12/license.html)

**Source:** https://github.com/python/cpython/tree/v3.12.7
**SHA-256 (source archive):** `0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459`

**Local notice:** `novel/game/python-packages/NOTICE.txt`

---

## Ren'Py 8.5.3 — MIT License

**Component:** Ren'Py 8.5.3 Visual Novel Engine

**License:** MIT License

Copyright (c) 2004-2024 Tom Rothamel

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**SDK license:** `C:\DEV\Narrative\renpy-8.5.3-sdk\LICENSE.txt`

---

## LLVM-MinGW 20241217 — Apache 2.0 with LLVM Exceptions

**Component:** LLVM-MinGW 20241217 (build toolchain, not distributed with game)

**License:** Apache License 2.0 with LLVM Exceptions
(https://github.com/mstorsjo/llvm-mingw)

**Binary SHA-256 (toolchain archive):** `f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7`

---

## Distribution Notes

- `_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd` is distributed as part of the
  game package under `game/python-packages/`. It statically links SQLite 3.45.3
  and wraps it with CPython 3.12.7 `_sqlite3` native code.
- All third-party license notices are reproduced in full at
  `novel/game/python-packages/NOTICE.txt`.
- The LLVM-MinGW toolchain is used only for deterministic rebuilds and is
  **not** distributed with the game.

---

*Last updated: 2026-08-06 — ASIDE V2 SLICE 2 SQLITE CORRECTION SLICE B*