#!/usr/bin/env python3
"""Prompt-cache test for llama-server on the real Kot (glow_readings) prompt shape: fixed system + variable user.
Usage: python llm-cache-test.py --url http://saiga-llm:5000/v1/chat/completions --system kot-system.txt --out DIR
1) timing: same system, different users, cache_prompt on vs off -> prompt_n / prompt_ms / cache_n from `timings`
2) determinism: temperature 0, identical request, cache off vs cache on (full hit) -> are texts identical, where they diverge
"""
import argparse, json, os, time, urllib.request

RAG = ("[Нумерология. Числа] Число {a} — архетип лидера и первопроходца: воля, инициатива, умение начинать с нуля. "
       "Теневая сторона — нетерпение и упрямство. Число {b} — число чувствительности, партнёрства и дипломатии, "
       "умения слышать других. Тень — зависимость от чужой оценки. Число {c} — творческое самовыражение, слово, "
       "лёгкость и радость, но и разбросанность.\n\n---\n\n[Нумерология. Совместимость чисел] Сочетание чисел "
       "показывает, где энергии усиливают друг друга, а где возникает внутренний конфликт между мотивом и проявлением.")

def user_prompt(a, b, c):
    return "\n".join([f"Число пути жизни: {a}", f"Число души: {b}", f"Число выражения: {c}", "",
                      "Контекст из базы знаний:", RAG.format(a=a, b=b, c=c), "",
                      "Сделай разбор по правилам системного сообщения."])

def call(url, system, user, cache, temperature=0.7, max_tokens=700, seed=None):
    p = {"model": "saiga", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
         "max_tokens": max_tokens, "temperature": temperature, "stream": False, "cache_prompt": cache}
    if seed is not None:
        p["seed"] = seed
    req = urllib.request.Request(url, data=json.dumps(p).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    return time.time() - t0, r.get("timings", {}), r["choices"][0]["message"]["content"]

def fmt(t):
    keys = ("cache_n", "prompt_n", "prompt_ms", "predicted_n", "predicted_per_second")
    return " ".join(f"{k}={round(t[k], 1) if isinstance(t.get(k), float) else t.get(k)}" for k in keys)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--system", required=True)
    ap.add_argument("--out", default="/tmp/cache-test")
    a = ap.parse_args()
    system = open(a.system, encoding="utf-8").read()
    os.makedirs(a.out, exist_ok=True)

    print("== timing (sequential; first call of each block warms/evicts) ==")
    for cache in (False, True, True, False, True):
        for nums in ((1, 2, 3), (7, 5, 9)):
            el, t, _ = call(a.url, system, user_prompt(*nums), cache, max_tokens=60)
            print(f"cache_prompt={cache!s:5} nums={nums} wall={el:.2f}s {fmt(t)}")

    print("== determinism (temperature 0) ==")
    u = user_prompt(4, 11, 6)
    _, t0, off = call(a.url, system, u, False, temperature=0, seed=42)
    _, t3, off2 = call(a.url, system, u, False, temperature=0, seed=42)  # control: same request, no cache, again
    _, t1, on1 = call(a.url, system, u, True, temperature=0, seed=42)   # fills cache
    _, t2, on2 = call(a.url, system, u, True, temperature=0, seed=42)   # full prefix hit
    for name, txt, t in (("off", off, t0), ("off2", off2, t3), ("on_fill", on1, t1), ("on_hit", on2, t2)):
        open(f"{a.out}/det-{name}.txt", "w", encoding="utf-8").write(txt)
        print(f"{name:8} len={len(txt)} {fmt(t)}")
    for name, txt in (("off2", off2), ("on_fill", on1), ("on_hit", on2)):
        if txt == off:
            print(f"off vs {name}: IDENTICAL")
        else:
            i = next((k for k in range(min(len(txt), len(off))) if txt[k] != off[k]), min(len(txt), len(off)))
            print(f"off vs {name}: diverge at char {i} of {len(off)}: ...{off[max(0, i - 40):i + 30]!r} | {txt[max(0, i - 40):i + 30]!r}")

if __name__ == "__main__":
    main()
