#!/usr/bin/env python3
"""Replace the `imagegen.vaibkod.ru { ... }` site block in a Caddyfile with the contents of a block file."""
import sys, shutil, datetime
caddyfile, blockfile = sys.argv[1], sys.argv[2]
lines = open(caddyfile, encoding="utf-8").read().split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("imagegen.vaibkod.ru {"))
end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
new = open(blockfile, encoding="utf-8").read().rstrip("\n").split("\n")
backup = caddyfile + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy(caddyfile, backup)
out = lines[:start] + new + lines[end + 1:]
open(caddyfile, "w", encoding="utf-8").write("\n".join(out))
print(f"replaced lines {start + 1}-{end + 1} ({end - start + 1} lines) with {len(new)} lines; backup {backup}")
