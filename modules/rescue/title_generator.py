"""YouTube metadata'sından dramatik Türkçe overlay başlığı + hook cümlesi üretimi."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

TITLE_HOOK_SYSTEM = """Sen viral TikTok / Reels için dramatik içerik yazarısın.
Verilen YouTube video başlığı ve açıklamasından İKİ ŞEY üret:

1. OVERLAY BAŞLIĞI (title): Videonun üstüne konulacak kısa, vurucu yazı.
2. HOOK CÜMLESİ (hook): Videonun ilk 3 saniyesinde seslendirilecek merak uyandıran cümle.

## OVERLAY BAŞLIĞI KURALLARI:
- Maksimum 6-8 kelime. Kısa ve vurucu.
- BÜYÜK HARF kullanılacak.
- Ünlem işareti ile bitir.
- Somut ve spesifik ol.
- İYİ: "POLİSLER SON ANDA YETİŞTİ!", "KURTARMA EKİBİ İMKANSIZI BAŞARDI!"
- KÖTÜ: "İnanılmaz bir video", "Şok edici anlar" (çok genel)

## HOOK CÜMLESİ KURALLARI:
- Tek cümle, maksimum 12-15 kelime.
- Videonun sonucuna dair merak uyandırmalı — izleyici "ne olacak?" demeli.
- Doğrudan olaya atıfta bulun, genel konuşma.
- Normal cümle, büyük harf değil (seslendirilecek).
- Anlatıcı tonu: ciddi, dramatik, heyecanlı.

İYİ HOOK ÖRNEKLERİ:
- "Bu adam yetişmeseydi, her şey kötü sonuçlanabilirdi."
- "Kimse fark etmedi ama kamera her şeyi kaydediyordu."
- "Ekip ulaştığında sadece birkaç dakikaları kalmıştı."
- "Herkes vazgeçmişti ama bir kişi pes etmedi."
- "O an bir saniye bile geç kalsaydı, sonuç çok farklı olurdu."

KÖTÜ HOOK ÖRNEKLERİ (YAPMA):
- "Bu videoyu sonuna kadar izleyin." (ucuz CTA)
- "İnanılmaz bir olay yaşandı." (çok genel)
- "Şimdi izleyeceklerinize inanamayacaksınız." (klişe)

Yanıtın YALNIZCA geçerli JSON olsun:
{"title": "DRAMATİK BAŞLIK!", "hook": "Hook cümlesi burada."}"""


@dataclass
class TitleAndHook:
    title: str
    hook: str


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def generate_title_and_hook(
    *,
    video_title: str,
    video_description: str,
    api_key: str,
    model: str,
) -> TitleAndHook:
    """YouTube metadata'sından dramatik overlay başlığı + hook cümlesi üret."""
    client = OpenAI(api_key=api_key)
    user_msg = f"""Video başlığı: {video_title}
Video açıklaması (ilk 500 karakter): {video_description[:500]}

Bu video için dramatik bir overlay başlığı ve hook cümlesi üret."""

    resp = client.chat.completions.create(
        model=model,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TITLE_HOOK_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)

    title = data.get("title", "").strip()
    hook = data.get("hook", "").strip()

    if not title:
        title = video_title.upper()[:50] + "!"
    if not hook:
        hook = "Bu anı kaçırmayın."

    logger.info("Başlık: %s", title)
    logger.info("Hook: %s", hook)
    return TitleAndHook(title=title, hook=hook)
