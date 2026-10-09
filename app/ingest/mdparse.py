"""Markdown -> steps + candidate lines. Pure code, no AI (AI_PROMPTS.md section 1, D-06)."""
import re

TITLE_MAX = 120
STEP_MAX = 30

_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
# "## x" per Markdown; "##x" (2+ hashes, no space) is accepted too. "#x" stays text (hashtags).
_HEAD = re.compile(r"^(#{1,6})(?:\s+|(?<=##)(?=[^\s#]))(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_LINK_ONLY = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[[^\]]*\]\([^)]*\)|<?https?://\S+>?)\s*$")
_CHECK = re.compile(r"^\[( |x|X)\]\s+")
_STEP_PREFIX = re.compile(r"^\s*(?:step\s*\d+\s*[:.\-–—]?\s*|later\s*[:\-–—]\s*)", re.I)


def _plain(s):
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = s.replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


def clean_title(s, limit=TITLE_MAX):
    s = _plain(_CHECK.sub("", s.strip()))
    return s.rstrip(":").strip()[:limit].rstrip()


def _cap(s):
    return s[:1].upper() + s[1:]


def clean_step(s):
    s = _STEP_PREFIX.sub("", s)
    s = _plain(re.sub(r"\([^)]*\)", " ", s)).rstrip(":").strip()
    if len(s) > STEP_MAX:
        cut = s[:STEP_MAX]
        if s[STEP_MAX] != " " and " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        s = cut.rstrip()
    return _cap(s)


def _sentences(p):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", p) if x.strip()]


def _strip_front_matter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def parse(text, kind="md"):
    """Return {title, candidates}. Candidate: {step, text, notes, from} with from = list | heading | prose.
    kind='text' (pasted) turns paragraph sentences into prose candidates only when it has no list items."""
    lines = _strip_front_matter(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    title = ""
    sections = []   # {step, heading, items:[{text,notes}], paras:[str], code:bool, content:bool}

    def new_section(step, heading):
        sections.append({"step": step, "heading": heading, "items": [], "paras": [], "code": False, "content": False})
        return sections[-1]

    cur = new_section("", "")
    in_code = in_comment = False
    item = None        # current top-level item (or skipped checked item)
    base = None        # indent of top-level items in the current list
    para = []

    def flush_para():
        if para:
            cur["paras"].append(" ".join(para))
            cur["content"] = True
            para.clear()

    for raw in lines:
        if in_code:
            if _FENCE.match(raw):
                in_code = False
            continue
        if in_comment:
            if "-->" in raw:
                in_comment = False
            continue
        s = raw.strip()
        if s.startswith("<!--"):
            if "-->" not in s:
                in_comment = True
            continue
        if _FENCE.match(raw):
            flush_para()
            in_code = True
            cur["code"] = cur["content"] = True
            continue
        if not s:
            flush_para()
            continue
        if s.startswith("|") or re.fullmatch(r"[-*_]{3,}", s) or _LINK_ONLY.match(raw):
            flush_para()
            continue
        h = _HEAD.match(s)
        if h:
            flush_para()
            level, htxt = len(h.group(1)), h.group(2)
            if level == 1:
                title = title or clean_title(htxt)
            elif level == 2:
                cur = new_section(clean_step(htxt), _cap(clean_title(_STEP_PREFIX.sub("", re.sub(r"\([^)]*\)", " ", htxt)))))
                item = base = None
            continue
        m = _ITEM.match(raw)
        if m:
            flush_para()
            indent, body = len(m.group(1).replace("\t", "    ")), m.group(3)
            if base is None or indent <= base:
                base = indent
                cur["content"] = True
                chk = _CHECK.match(body)
                if chk and chk.group(1) in "xX":
                    item = {"skip": True}
                else:
                    item = {"text": clean_title(body), "notes": []}
                    cur["items"].append(item)
            elif item is not None and not item.get("skip"):
                item["notes"].append(clean_title(body, 400))
            continue
        if raw[:1] in " \t" and item is not None:      # indented continuation of a list item
            if not item.get("skip"):
                item["notes"].append(clean_title(s, 400))
            continue
        item = base = None
        para.append(s)
    flush_para()

    has_lists = any(sec["items"] for sec in sections)
    cands = []
    for sec in sections:
        found = []
        for it in sec["items"]:
            if it["text"]:
                found.append({"step": sec["step"], "text": it["text"], "notes": "\n".join(it["notes"]), "from": "list"})
        if kind == "text" and not has_lists:
            for p in sec["paras"]:
                for sent in _sentences(p):
                    found.append({"step": sec["step"], "text": clean_title(sent), "notes": "", "from": "prose"})
        if not found and sec["heading"] and sec["content"]:
            found.append({"step": sec["step"], "text": sec["heading"], "notes": "", "from": "heading"})
        cands.extend(found)
    for i, c in enumerate(cands, 1):
        c["id"] = f"L{i}"
    return {"title": title, "candidates": cands}
