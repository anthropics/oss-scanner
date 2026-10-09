# Threat model

## What this project does and where untrusted input enters
- php_excel is a PHP extension (`excel.c`, `php_excel.h`, `libxl_compat.h`) that wraps LibXL, a closed-source commercial C/C++ library for reading and writing XLS/XLSX. It exposes `ExcelBook`, `ExcelSheet`, `ExcelFormat`, `ExcelFont`, `ExcelAutoFilter`, `ExcelFilterColumn`, `ExcelRichString`, `ExcelFormControl`, `ExcelConditionalFormat(ting)`, `ExcelCoreProperties`, and `ExcelTable`.
- The primary attacker is whoever supplies a spreadsheet: assume any XLS/XLSX passed to `ExcelBook::load()`, `loadFile()`, `loadPartially()`, `loadFilePartially()`, `loadFileWithoutEmptyCells()`, `loadInfo()`, or `loadInfoRaw()` is hostile. Everything read back out of a loaded book is attacker data: cell values, strings, rich strings, formulas, comments, merges, named ranges, hyperlinks, pictures (`getPicture()`, `getPictureInfo()`), data validations, form controls, autofilters, tables, core properties, and declared dimensions or counts.
- The second source is cell data and arguments from userland written by an application on behalf of a user: strings, arrays passed to `writeRow()`/`writeCol()`, picture bytes passed to `addPictureFromString()`, and row/column/index integers that an application may take from a request.
- The wrapper's job is to convert between LibXL handles and buffers and Zend values. The bugs we care about are in that conversion: trusting LibXL-reported lengths, counts, or indexes; integer overflow when sizing arrays or strings; signed/unsigned and `int`/`size_t` narrowing; NUL handling; object lifetime between a book and the sheets, formats, fonts, and filters that point into it (use after `ExcelBook` is freed or reloaded); and arginfo/ZPP mismatches.

## Components that matter most / least
- In scope: everything in `excel.c`, `php_excel.h`, and `libxl_compat.h`. The load and read paths matter most, then object lifetime across book reloads and sheet deletion, then the write and picture paths.
- Out of scope: LibXL itself (`/opt/libxl`, installed from libxl.com at build time). It is closed-source; its bugs are reported to XLware, not here. Do not disassemble, decompile, or reverse engineer `libxl.so`: its license forbids it. A crash inside `libxl.so` is in scope only when the wrapper caused it, for example by passing an out-of-range index, a dangling handle, or a wrong length.
- Out of scope: `docs/` (PHP stubs for IDEs), `tests/`, `config.w32`, and the license-key mechanism itself beyond the wrapper's own handling of the `excel.license_name`/`excel.license_key` INI strings.

## How to exercise it
- The image has the module at `/src/modules/excel.so` (also installed, so `php -d extension=excel` works) and LibXL at `/opt/libxl/lib64` (registered with `ldconfig`).
- `run-phpt` runs the PHPT suite; pass test paths or `run-tests.php` flags to narrow it, for example `run-phpt tests/219_loadinforaw_empty_string.phpt`.
- Minimal driver: `php -d extension=excel -r '$b = new ExcelBook(null, null, true); var_dump($b->loadFile($argv[1])); $s = $b->getSheet(0); var_dump($s->readRow(1));' file.xlsx`. `new ExcelBook(null, null, false)` gives an XLS book.
- `tests/datavalidation.xlsx` and `tests/formcontrols.xlsx` are small seed files. Crafted inputs can be produced by writing a book with the extension, then editing the XLSX ZIP/XML or the XLS BIFF records.
- LibXL runs in trial mode (no license key): it writes a banner into row 0 of saved books and limits how many cells it reads (~300 per book). Avoid row 0 and keep reproducers small; a reproducer that needs a licensed LibXL is still acceptable if the wrapper bug is clear from the code.
- For memory errors, run under valgrind with `USE_ZEND_ALLOC=0`. LibXL is C++; if ASan is used, `LD_PRELOAD` libstdc++ so its exceptions unwind.

## How you rate severity
- Critical: memory corruption reachable from an untrusted spreadsheet that gives a controlled write (attacker-chosen offset or contents).
- High: any other out-of-bounds write, use-after-free, or double free reachable from an untrusted spreadsheet or from cell data an application writes on a user's behalf.
- Medium to high: out-of-bounds read or information leak (heap bytes returned to PHP as cell text, picture data, or array contents) from an untrusted spreadsheet.
- Medium: crash, NULL dereference, assertion failure, or uncaught C++ exception escaping into PHP on a malformed spreadsheet.
- Low to medium: resource exhaustion (memory, CPU) from a small malformed file, beyond the documented full buffering of the input.
- Low or out of scope: bugs that need attacker-controlled PHP code, attacker-controlled INI settings (`excel.skip_empty`, license INI), or an application that passes attacker-chosen row/column indexes without validation and then only gets a PHP-level error. Formula injection via implicit `=` promotion in `write()` is documented behavior (SECURITY.md), not a finding.

## Anything to leave alone
- Do not report LibXL trial-mode limits (banner row, cell cap, "requires key" behavior) as bugs.
- Leaks attributed to LibXL internals (see `.github/lsan-suppressions.txt`) are known and out of scope.
- Do not report that `addPictureAsLink()` or `addHyperlink()` store caller-supplied UNC paths or URLs verbatim; SECURITY.md documents this.
