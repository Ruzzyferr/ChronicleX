"""Vizyona girecek korku filmi önerisi + interaktif seçim."""

from __future__ import annotations

import json
import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

HORROR_SUGGEST_SYSTEM = """Sen dünyanın en iyi korku filmi uzmanısın.
Vizyona yeni girmiş veya yakında girecek korku filmlerini takip ediyorsun.

Kullanıcıya TAM 3 korku filmi öner. Her öneri:
- 2025-2026 yapımı veya vizyona yeni girmiş/girecek olmalı
- Gerçekten var olan, IMDb'de bulunan filmler olmalı — uydurma YASAK
- Trailer'ı YouTube'da bulunabilir olmalı
- Farklı alt türlerden olsun (slasher, supernatural, psychological horror, folk horror, creature vb.)

Her film için:
- title: Filmin orijinal İngilizce adı (trailer aramada kullanılacak)
- title_tr: Türkçe adı (varsa, yoksa orijinal adını yaz)
- year: Yapım yılı
- genre: Alt tür (1-2 kelime: supernatural, slasher, psychological vb.)
- hook: Filmin trailerının başına konulacak merak uyandırıcı TEK CÜMLE (Türkçe, max 12 kelime)
  - DOĞRU: "Bu filmi sinemada tek başına izlemeye cesaret edemezsin."
  - DOĞRU: "Yönetmen seti o kadar gerçekçi yaptı ki oyuncular gerçekten korktu."
  - DOĞRU: "İlk gösterimde 30 kişi salondan kaçtı."
  - YANLIŞ: "Korkunç bir film." (çok genel)
- why: Neden izlenmeli — 1 cümle

Yanıtın YALNIZCA geçerli JSON olsun:
{"movies": [{"title": "English Title", "title_tr": "Türkçe Ad", "year": 2025, "genre": "supernatural", "hook": "Hook cümlesi.", "why": "Neden izlenmeli."}, ...]}"""


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def suggest_horror_movies(*, api_key: str, model: str) -> list[dict[str, str]]:
    """OpenAI'dan 3 vizyondaki korku filmi önerisi al."""
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.8,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": HORROR_SUGGEST_SYSTEM},
            {"role": "user", "content": "Bana vizyona yeni girmiş veya yakında girecek 3 korku filmi öner."},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    return data.get("movies", [])


def interactive_movie_select(*, api_key: str, model: str) -> tuple[str, str]:
    """Terminal'de 3 korku filmi göster, seçim al.

    Returns:
        (film_title_en, hook_text) — İngilizce başlık (trailer arama) ve hook cümlesi
    """
    movies = suggest_horror_movies(api_key=api_key, model=model)

    print("\n" + "=" * 60)
    print("  KORKU FİLMİ — Trailer Seçimi")
    print("=" * 60)

    for i, m in enumerate(movies, 1):
        title_tr = m.get("title_tr", m.get("title", "?"))
        title_en = m.get("title", "?")
        year = m.get("year", "?")
        genre = m.get("genre", "?")
        hook = m.get("hook", "")
        why = m.get("why", "")
        print(f"\n  [{i}] {title_tr} ({title_en}, {year}) — {genre}")
        print(f"      Hook: {hook}")
        print(f"      {why}")

    print(f"\n  [4] Kendi filmimi yazacağım")
    print("=" * 60)

    while True:
        choice = input("\n  Seçimin (1/2/3/4): ").strip()
        if choice in ("1", "2", "3"):
            idx = int(choice) - 1
            if idx < len(movies):
                m = movies[idx]
                title_en = m.get("title", "")
                hook = m.get("hook", "Bu filmi kaçırma.")
                title_tr = m.get("title_tr", title_en)
                print(f"\n  Seçildi: {title_tr}")
                return title_en, hook
        elif choice == "4":
            custom = input("  Film adını yaz (İngilizce): ").strip()
            if custom:
                custom_hook = input("  Hook cümlesi (opsiyonel, boş bırakabilirsin): ").strip()
                if not custom_hook:
                    custom_hook = "Bu filmi sinemada izlemeye cesaret edebilir misin?"
                print(f"\n  Seçildi: {custom}")
                return custom, custom_hook
            print("  Boş isim giremezsin, tekrar dene.")
        else:
            print("  Geçersiz seçim, tekrar dene.")
