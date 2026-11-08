#!/usr/bin/env python3
"""Q4 vs Q5: 12 реальных промптов Кота (kot-prompts.json из healspirit) × repeats, параллельно --conc,
тексты в OUT/<label>-<i>-<r>.txt, затем орфография через hunspell -d ru_RU.
  python3 quant_test.py run --url URL --label q4 --out DIR [--repeats 2 --conc 3]
  python3 quant_test.py spell --out DIR
"""
EXTRA = {}
import argparse, collections, glob, json, os, re, subprocess, threading, time, urllib.request


def call(url, system, user):
    p = {"model": "saiga", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
         "max_tokens": 2500, "temperature": 0.7, "stream": False, **EXTRA}
    req = urllib.request.Request(url, data=json.dumps(p).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    return r["choices"][0]["message"]["content"], r.get("timings", {})


def run(a):
    prompts = json.load(open(a.prompts, encoding="utf-8"))
    jobs = [(i, r) for r in range(a.repeats) for i in range(len(prompts))]
    lock, tps = threading.Lock(), []
    os.makedirs(a.out, exist_ok=True)

    def worker():
        while True:
            with lock:
                if not jobs:
                    return
                i, r = jobs.pop(0)
            text, t = call(a.url, prompts[i]["system"], prompts[i]["user"])
            open(f"{a.out}/{a.label}-{i:02d}-{r}.txt", "w", encoding="utf-8").write(text)
            with lock:
                tps.append(t.get("predicted_per_second") or 0)

    t0 = time.time()
    th = [threading.Thread(target=worker) for _ in range(a.conc)]
    [t.start() for t in th]
    [t.join() for t in th]
    print(f"[{a.label}] {len(tps)} texts in {time.time() - t0:.0f}s, per-stream {sum(tps) / len(tps):.1f} tok/s")


def spell(a):
    words_re = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")
    by_label = collections.defaultdict(lambda: [0, 0, collections.Counter()])
    for f in sorted(glob.glob(f"{a.out}/*.txt")):
        label = os.path.basename(f).split("-")[0]
        text = open(f, encoding="utf-8").read()
        words = words_re.findall(text)
        bad = subprocess.run(["hunspell", "-d", "ru_RU", "-l"], input=" ".join(words), capture_output=True,
                             text=True).stdout.split()
        s = by_label[label]
        s[0] += len(words)
        s[1] += len(bad)
        s[2].update(w.lower() for w in bad)
    for label, (n, b, c) in sorted(by_label.items()):
        print(f"[{label}] words {n}, flagged {b} = {1000 * b / n:.1f} на 1000 слов")
        print("   ", ", ".join(f"{w}×{k}" if k > 1 else w for w, k in c.most_common(60)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("run", "spell"))
    ap.add_argument("--url"); ap.add_argument("--label"); ap.add_argument("--out", required=True)
    ap.add_argument("--prompts", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kot-prompts.json"))
    ap.add_argument("--repeats", type=int, default=2); ap.add_argument("--conc", type=int, default=3)
    ap.add_argument("--min-p", type=float); ap.add_argument("--top-p", type=float)
    a = ap.parse_args()
    if a.min_p is not None: EXTRA["min_p"] = a.min_p
    if a.top_p is not None: EXTRA["top_p"] = a.top_p
    (run if a.mode == "run" else spell)(a)


if __name__ == "__main__":
    main()
