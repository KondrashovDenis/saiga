#!/usr/bin/env python3
"""LLM throughput bench against an OpenAI-compatible chat endpoint (inside the docker network, no auth).
Usage: python llm-bench.py --url http://saiga-llm:5000/v1/chat/completions --label ooba --out /tmp/bench
Runs: 1 request alone, then N concurrent. Saves each answer to <out>/<label>-<run>-<i>.txt.
"""
import argparse, json, os, time, threading, urllib.request

SYSTEM = ("Ты — опытный нумеролог и мастер мягкой поддержки. Отвечай по-русски, тепло, образно и структурированно: "
          "короткое вступление, затем разделы с подзаголовками, в конце — практический совет на ближайший месяц.")
USERS = [
    "Сделай нумерологический разбор для даты рождения 14.03.1987, имя Анна. Число судьбы, сильные стороны, уроки, отношения, работа.",
    "Сделай нумерологический разбор для даты рождения 02.11.1979, имя Денис. Число судьбы, сильные стороны, уроки, отношения, работа.",
    "Сделай нумерологический разбор для даты рождения 27.07.1995, имя Мария. Число судьбы, сильные стороны, уроки, отношения, работа.",
    "Сделай нумерологический разбор для даты рождения 09.01.2001, имя Илья. Число судьбы, сильные стороны, уроки, отношения, работа.",
]

def one(url, user, max_tokens, res, idx):
    payload = {"model": "saiga", "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
               "max_tokens": max_tokens, "temperature": 0.7, "stream": False}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=900).read())
        el = time.time() - t0
        u = r.get("usage", {})
        res[idx] = (el, u.get("prompt_tokens"), u.get("completion_tokens"), r["choices"][0]["message"]["content"])
    except Exception as e:
        res[idx] = (time.time() - t0, None, None, f"ERROR {e}")

def run(url, users, max_tokens):
    res = [None] * len(users)
    th = [threading.Thread(target=one, args=(url, u, max_tokens, res, i)) for i, u in enumerate(users)]
    t0 = time.time()
    for t in th: t.start()
    for t in th: t.join()
    return time.time() - t0, res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--out", default="/tmp/bench"); ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=900)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name, users in (("single", USERS[:1]), (f"concurrent{a.n}", USERS[:a.n])):
        wall, res = run(a.url, users, a.max_tokens)
        total = sum((r[2] or 0) for r in res)
        print(f"[{a.label}] {name}: wall {wall:.1f}s, total completion tokens {total}, aggregate {total / wall:.1f} tok/s")
        for i, (el, pt, ct, text) in enumerate(res):
            print(f"   req{i}: {el:.1f}s prompt={pt} completion={ct} -> {((ct or 0) / el):.1f} tok/s{'' if ct else ' ' + text[:120]}")
            open(f"{a.out}/{a.label}-{name}-{i}.txt", "w", encoding="utf-8").write(text)

if __name__ == "__main__":
    main()
