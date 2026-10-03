"""Parse the reader stylesheet into (at-rule context, selectors, body) so style guards
assert a rule exists where it must, not that a substring appears somewhere."""
import re
from scripts.render.reader.theme import CSS


def rules(css=CSS):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, stack, buf, i = [], [], "", 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            head = buf.strip()
            if head.startswith("@"):
                stack.append(head)
            else:
                j = css.index("}", i)
                out.append((tuple(stack), [s.strip() for s in head.split(",")], css[i + 1:j]))
                i = j
            buf = ""
        elif ch == "}":
            if stack:
                stack.pop()
            buf = ""
        else:
            buf += ch
        i += 1
    return out


def has(sel, prop, media=None, supports=None):
    for ctx, sels, body in rules():
        m = any(c.startswith("@media (max-width:1023px)") for c in ctx) if media == "max" else \
            any(c.startswith("@media (min-width:1024px)") for c in ctx) if media == "min" else True
        s = any(c.startswith("@supports") and supports in c for c in ctx) if supports else True
        if sel in sels and prop in body and m and s:
            return True
    return False
