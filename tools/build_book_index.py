# -*- coding: utf-8 -*-
"""Сборка longevity/data/books.json из MOBI-книг А. А. Москалева.

Пайплайн на одну книгу:
  1. ebook-convert (calibre) перегоняет .mobi в epub.
  2. content.opf даёт порядок XHTML-файлов (spine) и метаданные книги,
     toc.ncx — оглавление: раздел занимает файл целиком или якорь внутри.
  3. Абзацы читаются по spine; раздел абзаца — ближайшая точка оглавления,
     встреченная раньше в порядке документа.
  4. Абзацы нарезаются на отрывки ~CHUNK_CHARS знаков (граница раздела
     всегда завершает отрывок) и пишутся в longevity/data/books.json.

books.json — единственное, что приложение читает во время работы;
сами .mobi в git не попадают (см. .gitignore).

Запуск из корня репозитория:
    python3 tools/build_book_index.py [*.mobi ...]
Без аргументов берутся все *.mobi в корне репозитория.
"""

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "longevity" / "data" / "books.json"

#: Целевой размер отрывка в знаках — единица выдачи и контекста промпта.
CHUNK_CHARS = 1500
#: Абзац длиннее этого режется по предложениям (редкие «простыни»).
MAX_CHUNK_CHARS = 3000
#: Отрывки короче этого выкидываются как обрезки.
MIN_PASSAGE_CHARS = 200

#: Известные книги: префикс названия (после нормализации) -> (id, короткое имя).
#: Стабильные id нужны, чтобы пересборка не меняла ссылки внутри базы.
KNOWN_BOOKS = (
    ("120 лет жизни - только начало",
     "kniga-120-let", "120 лет жизни"),
    ("мозг долгожителя",
     "mozg-dolgozhitelya", "Мозг долгожителя"),
    ("кишечник долгожителя",
     "kishechnik-dolgozhitelya", "Кишечник долгожителя"),
)

_CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюяё"
_LATIN = "abvgdezhziyklmnoprstufhtschshsch'y'eyua-e"
_SKIP_PARA = re.compile(r"^\s*(cover|обложк)\s*$", re.I)

# Служебные разделы: блёрбы, выходные данные и примечания-словари не несут
# рекомендаций и только засоряют поиск и контекст.
_SERVICE_SECTIONS = {"Отзывы", "Аннотация", "Выходные данные", "Обложка",
                     "Информация об авторе", "Примечания", "Список литературы"}
# Сноски-глоссарии в конце книг начинаются с номера без точки: «18 АТФ – …».
# Нумерованные же рекомендации оформлены как «1. …» и под правило не попадают.
_GLOSSARY_RE = re.compile(r"^\d{1,3}\s+[A-ZА-ЯЁ]")
_CREDIT_MARKERS = (
    "shutterstock", "фото:", "фотобанк", "все права защищены",
    "использованы иллюстрации", "оформлении использованы",
    "дизайн обложки", "isbn", "переиздание", "©",
)


def _clean(raw: str) -> str:
    """Служебные пробелы/переносы -> обычные, всё схлопнуть в один пробел."""
    text = html.unescape(raw)
    text = text.replace("\u00a0", " ").replace("\u2009", " ")
    text = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------------
# Оглавление epub (toc.ncx)
# ----------------------------------------------------------------------
@dataclass
class NavNode:
    """Раздел оглавления: файл, якорь, название, путь от корня."""
    file: str = ""
    anchor: str | None = None
    label: str = ""
    path: tuple[str, ...] = ()


class _NcxParser(HTMLParser):
    """navMap -> плоский список NavNode в порядке документа."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes: list[NavNode] = []
        self._stack: list[tuple[NavNode, tuple[str, ...]]] = []
        self._label_buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "navpoint":
            ancestors = ()
            if self._stack:
                parent, parent_path = self._stack[-1]
                ancestors = parent_path + ((parent.label,) if parent.label else ())
            node = NavNode()
            self._stack.append((node, ancestors))
        elif tag == "text" and self._stack:
            self._label_buf = []
        elif tag == "content" and self._stack:
            src = dict(attrs).get("src", "")
            file_, _, anchor = src.partition("#")
            node, _ = self._stack[-1]
            node.file = file_.lstrip("./")
            node.anchor = anchor or None

    def handle_data(self, data):
        if self._label_buf is not None:
            self._label_buf.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "text" and self._label_buf is not None and self._stack:
            node, _ = self._stack[-1]
            node.label = _clean("".join(self._label_buf))
            self._label_buf = None
        elif tag == "navpoint" and self._stack:
            node, ancestors = self._stack.pop()
            node.path = ancestors + ((node.label,) if node.label else ())
            if node.file:
                self.nodes.append(node)


def _read_toc(ncx: Path) -> list[NavNode]:
    parser = _NcxParser()
    parser.feed(ncx.read_text(encoding="utf-8", errors="replace"))
    return parser.nodes


# ----------------------------------------------------------------------
# Текст книги: XHTML-файлы epub -> абзацы
# ----------------------------------------------------------------------
@dataclass
class Para:
    """Абзац: текст и раздел оглавления, действующий с этого места."""
    text: str
    section: tuple[str, ...] = ()
    anchor: str | None = None


class _TextParser(HTMLParser):
    """Абзацы XHTML-файла; оформление и служебные теги пропускаются."""

    BLOCK_END = {"p", "h1", "h2", "h3", "h4", "h5", "h6",
                 "li", "dt", "dd", "blockquote", "pre"}
    SKIP = {"script", "style", "svg", "head"}

    def __init__(self, nav_anchors: set[str]):
        super().__init__(convert_charrefs=True)
        self._nav_anchors = nav_anchors
        self._skip = 0
        self._buf: list[str] = []
        self._anchor: str | None = None
        self.paragraphs: list[Para] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        anchor = dict(attrs).get("id")
        if anchor in self._nav_anchors:
            self._anchor = anchor

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP:
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag in self.BLOCK_END:
            text = _clean("".join(self._buf))
            self._buf = []
            if text and not _SKIP_PARA.search(text):
                self.paragraphs.append(Para(text, anchor=self._anchor))

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)


def _read_paragraphs(text_dir: Path, spine: list[str],
                     by_file, by_anchor) -> list[Para]:
    """Все абзацы книги в порядке документа, с разделом каждого.

    Раздел — ближайшая точка оглавления раньше абзаца: файловый пункт
    действует с начала файла, якорь — с места своего появления.
    """
    result: list[Para] = []
    section: tuple[str, ...] | None = None
    for href in spine:
        part = text_dir / href
        if not part.is_file():
            continue
        if href in by_file:
            section = by_file[href]
        parser = _TextParser(set(by_anchor))
        parser.feed(part.read_text(encoding="utf-8", errors="replace"))
        for para in parser.paragraphs:
            if para.anchor in by_anchor:
                section = by_anchor[para.anchor]
            para.section = section or ()
        result.extend(parser.paragraphs)
    return result


def _is_service_paragraph(para) -> bool:
    """Мусорный абзац: блёрбы, выходные данные, сноски-словари, титулы.

    Решает, выкинуть ли абзац до нарезки на отрывки. Нумерованные
    рекомендации («1. Развивайте…») не задеваются: у сносок номер стоит
    без точки, у списков — с точкой.
    """
    text = para.text.strip()
    low = text.lower()
    if para.section and para.section[0] in _SERVICE_SECTIONS:
        return True
    if _GLOSSARY_RE.match(text):
        return True
    return any(marker in low for marker in _CREDIT_MARKERS)


def _read_toc_maps(ncx: Path):
    """Карты: файл -> раздел (для файловых пунктов), якорь -> раздел."""
    by_file, by_anchor = {}, {}
    for node in _read_toc(ncx):
        if node.anchor:
            by_anchor[node.anchor] = node.path
        elif node.file:
            by_file[node.file] = node.path
    return by_file, by_anchor


# ----------------------------------------------------------------------
# Нарезка абзацев на отрывки
# ----------------------------------------------------------------------
def _split_long(text: str) -> list[str]:
    """Абзац длиннее MAX_CHUNK_CHARS режется по границам предложений."""
    pieces, buf = [], ""
    for part in re.split(r"(?<=[.!?…])\s+", text):
        if buf and len(buf) + len(part) > MAX_CHUNK_CHARS:
            pieces.append(buf)
            buf = ""
        buf = (buf + " " + part).strip() if buf else part
        if len(buf) >= MAX_CHUNK_CHARS * 0.9:
            pieces.append(buf)
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces or [text]


def _chunk(paragraphs: list[Para]) -> list[tuple[str, str]]:
    """(section, text) отрывков: ~CHUNK_CHARS, не рвут абзац и раздел."""
    passages: list[tuple[str, str]] = []
    current: list[str] = []
    current_section = ""
    size = 0

    def flush():
        nonlocal current, size
        text = " ".join(current).strip()
        current, size = [], 0
        if len(text) >= MIN_PASSAGE_CHARS:
            passages.append((current_section, text))

    for para in paragraphs:
        # Заголовок раздела часто лежит и в тексте, и в оглавлении: дубль
        # внутри отрывка не нужен — источник и так укажет раздел.
        if para.text in set(para.section):
            continue
        section = " · ".join(para.section)
        if section != current_section:
            flush()
            current_section = section
        if len(para.text) > MAX_CHUNK_CHARS:
            flush()
            for piece in _split_long(para.text):
                if len(piece) >= MIN_PASSAGE_CHARS:
                    passages.append((current_section, piece))
            continue
        current.append(para.text)
        size += len(para.text)
        if size >= CHUNK_CHARS:
            flush()
    flush()
    return passages


# ----------------------------------------------------------------------
# Книга целиком: конвертация + отрывки
# ----------------------------------------------------------------------
def _convert(mobi: Path, epub: Path) -> None:
    result = subprocess.run(["ebook-convert", str(mobi), str(epub)],
                            capture_output=True, text=True)
    if result.returncode != 0 or not epub.exists():
        raise RuntimeError(
            f"ebook-convert не смог конвертировать {mobi.name}:\n"
            + (result.stderr or result.stdout)[-800:])


def _find_opf(base: Path) -> Path:
    found = sorted(base.rglob("content.opf"))
    if found:
        return found[0]
    xml = (base / "META-INF" / "container.xml").read_text(
        encoding="utf-8", errors="replace")
    m = re.search(r'full-path="([^"]+)"', xml)
    if not m:
        raise RuntimeError(f"в {base} не найден content.opf")
    return base / m.group(1)


def _read_opf(opf: Path) -> tuple[list[str], str, str]:
    """(spine, title, creator) из content.opf."""
    xml = opf.read_text(encoding="utf-8", errors="replace")
    manifest = dict(re.findall(r'<item\b[^>]*id="([^"]+)"[^>]*href="([^"]+)"', xml))
    spine = []
    for item_id in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', xml):
        href = manifest.get(item_id, "")
        if href.lower().endswith((".html", ".xhtml", ".htm")):
            spine.append(href)
    title = _dc(xml, "title")
    creator = _dc(xml, "creator")
    return spine, title, creator


def _dc(xml: str, tag: str) -> str:
    m = re.search(rf"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", xml, flags=re.S)
    return _clean(m.group(1)) if m else ""


def _meta(title: str, creator: str, mobi_name: str) -> dict:
    """Запись о книге со стабильным id по KNOWN_BOOKS."""
    norm = re.sub(r"\s+", " ", title.lower().replace("ё", "е")).strip()
    norm = re.sub(r"[\u2010-\u2015\u2212-]", "-", norm)
    for prefix, book_id, short in KNOWN_BOOKS:
        if norm.startswith(prefix):
            return {"id": book_id, "title": short, "subtitle": "",
                    "author": creator or "Алексей Москалев", "file": mobi_name}
    translit = norm.translate(str.maketrans(_CYRILLIC, _LATIN))
    book_id = re.sub(r"[^a-z0-9]+", "-", translit).strip("-") or "book"
    head = re.split(r"[.–]", title, maxsplit=1)
    return {"id": book_id, "title": head[0].strip(),
            "subtitle": (head[1].strip() if len(head) > 1 else ""),
            "author": creator or "Алексей Москалев", "file": mobi_name}


def _build_one(mobi: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="books-") as tmp:
        tmp = Path(tmp)
        epub = tmp / (mobi.stem + ".epub")
        _convert(mobi, epub)
        base = tmp / "unpacked"
        with zipfile.ZipFile(epub) as zf:
            for name in zf.namelist():
                target = base / name
                if name.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))

        opf_path = _find_opf(base)
        spine, title, creator = _read_opf(opf_path)
        ncx = next((p for p in (opf_path.parent / "toc.ncx", base / "toc.ncx")
                    if p.is_file()), None)
        by_file, by_anchor = _read_toc_maps(ncx) if ncx else ({}, {})
        paragraphs = _read_paragraphs(opf_path.parent, spine, by_file, by_anchor)
        paragraphs = [p for p in paragraphs if not _is_service_paragraph(p)]
        chunks = _chunk(paragraphs)
        # Сноски-определения нередко сливаются в свой отрывок, который
        # начинается с номера без точки: «11 Вызывающие атеросклероз…».
        chunks = [c for c in chunks if not _GLOSSARY_RE.match(c[1].strip())]
        # Титульные и выходные страницы до первого раздела оглавления.
        chunks = [c for c in chunks if c[0].strip()]
        meta = _meta(title, creator, mobi.name)
        passages = [
            {"id": f"{meta['id']}:{i:04d}",
             "book": meta["id"],
             "section": section,
             "text": text}
            for i, (section, text) in enumerate(chunks, 1)
        ]
        meta.pop("file")
        return {"book": meta, "passages": passages}


def build_all(mobi_files: list[Path]) -> dict:
    books, passages = [], []
    for mobi in sorted(mobi_files):
        one = _build_one(mobi)
        books.append(one["book"])
        passages.extend(one["passages"])
    return {"version": 1, "books": books, "passages": passages}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mobi", nargs="*", type=Path,
                        help="файлы .mobi (по умолчанию — все в корне)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    files = args.mobi or sorted(REPO_ROOT.glob("*.mobi"))
    if not files:
        print("Нет *.mobi в", REPO_ROOT, file=sys.stderr)
        return 1
    for mobi in files:
        if not mobi.is_file():
            print("Нет файла:", mobi, file=sys.stderr)
            return 1

    data = build_all(files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print(f"Книг: {len(data['books'])}, отрывков: {len(data['passages'])}, "
          f"знаков: {sum(len(p['text']) for p in data['passages']):,}")
    for book in data["books"]:
        bp = [p for p in data["passages"] if p["book"] == book["id"]]
        chars = sum(len(p["text"]) for p in bp)
        sections = len({p["section"] for p in bp if p["section"]})
        print(f"  {book['id']:<24} {len(bp):>5} отр. {chars:>8,} зн., "
              f"разделов: {sections:>3}  {book['title']}")
    print("->", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
