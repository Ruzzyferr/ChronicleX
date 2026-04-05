"""YouTube metadata'sından dramatik Türkçe overlay başlığı üretimi."""

from __future__ import annotations

import json
import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

TITLE_SYSTEM = """Sen viral TikTok / Reels için dramatik başlık yazarısın.
Verilen YouTube video başlığı ve açıklamasından, videonun üstüne konulacak
KISA, VURUCU, DRAMATİK bir Türkçe overlay yazısı üret.

KURALLAR:
- Maksimum 6-8 kelime. Kısa ve vurucu.
- BÜYÜK HARF kullanılacak.
- Ünlem işareti ile bitir.
- Somut ve spesifik ol — ne olduğunu hemen anlaşılsın.
- İzleyiciyi ilk saniyede yakalayacak şekilde yaz.

İYİ ÖRNEKLER:
- "POLİSLER SON ANDA YETİŞTİ!"
- "KURTARMA EKİBİ İMKANSIZI BAŞARDI!"
- "SUÇLU KAÇARKEN YAKALANDI!"
- "4 SAAT SONRA ENKAZDAN ÇIKARILDI!"
- "KAMERA HER ŞEYİ KAYDETTİ!"
- "SON SANİYEDE KURTULDU!"

KÖTÜ ÖRNEKLER (YAPMA):
- "İnanılmaz bir video" (çok genel)
- "Bu videoyu izlemelisiniz" (CTA değil başlık)
- "Şok edici anlar" (klişe)

Yanıtın YALNIZCA geçerli JSON olsun:
{"title": "DRAMATİK BAŞLIK BURADA!"}"""


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def generate_dramatic_title(
    *,
    video_title: str,
    video_description: str,
    api_key: str,
    model: str,
) -> str:
    """YouTube metadata'sından dramatik overlay başlığı üret."""
    client = OpenAI(api_key=api_key)
    user_msg = f"""Video başlığı: {video_title}
Video açıklaması (ilk 500 karakter): {video_description[:500]}

Bu video için dramatik bir overlay başlığı üret."""

    resp = client.chat.completions.create(
        model=model,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TITLE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    title = data.get("title", "").strip()

    if not title:
        # Fallback: video başlığını büyük harfe çevir
        title = video_title.upper()[:50] + "!"

    logger.info("Dramatik başlık üretildi: %s", title)
    return title
