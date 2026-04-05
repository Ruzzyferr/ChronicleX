"""URL'den vaka detayı çekip OpenAI ile dedektif tarzı anlatım + sahne görselleri üretir."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from core.media_models import Scene, ScenesLLMResponse
from core.models import TopicConfig
from modules.scripting.scene_generator import normalize_scenes

logger = logging.getLogger(__name__)

# Hassas kelime → kapalı ifade eşleştirmesi (LLM kaçırırsa post-process yakalar)
_SENSITIVE_REPLACEMENTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btecav[uü]z\b", re.IGNORECASE), "T. olayı"),
    (re.compile(r"\bcinsel\s+saldırı\b", re.IGNORECASE), "C.S. olayı"),
    (re.compile(r"\bcinsel\s+istismar\b", re.IGNORECASE), "istismar olayı"),
    (re.compile(r"\bcinsel\s+taciz\b", re.IGNORECASE), "taciz olayı"),
    (re.compile(r"\birza\s+geçme\b", re.IGNORECASE), "T. olayı"),
]


def _sanitize_sensitive_content(text: str) -> str:
    """Hassas kelimeleri kapalı ifadelerle değiştirir."""
    for pattern, replacement in _SENSITIVE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text

VAKA_NARRATION_SYSTEM = """Sen bir gerçek suç belgeseli (true crime) anlatıcısısın.
Verilen vaka içeriğini YALNIZCA belgelenen gerçeklere dayanarak izleyiciyi merakta bırakan
dedektif tarzı Türkçe kısa video senaryosuna dönüştür.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: ANLATIM METNİ (narration)

YAPI — bu sırayı takip et:
1. HOOK: İlk cümle — kim, ne zaman, nerede? Somut bir gerçekle anında merak uyandır.
2. OLAY: Tam olarak ne oldu? Her detayı ver — bulgu, konum, koşullar.
3. KİLİT İPUÇLARI: Her ipucunu ayrı bilgi olarak sun. Dedektif gibi:
   "X durumu şunu gösteriyordu..." / "Y bulgusu dikkat çekiciydi..."
4. ŞÜPHELİLER: Kim şüpheli? Neden? İsim, motivasyon, kanıt bağlantısı.
5. TEORİLER: Yetkililerin teorisi ne? Ailenin teorisi ne? Alternatifleri göster.
6. KAPANIŞ: İzleyiciyi yoruma davet et — "Sence ne oldu? Yoruma yaz." tarzı somut CTA.

KURALLAR:
- SADECE sağlanan vaka içeriğine dayan; hiçbir bilgi uydurma
- Her cümle somut bilgi içermeli: tarih, isim, yer, kanıt, sayı
- Felsefe ve metafor KESINLIKLE YASAK ("tarihin karanlık yüzü" vb.)
- "Biliyor muydunuz" tarzı ucuz hook YASAK — doğrudan olaya gir
- Her cümle bir sonraki soruyu doğurmalı — izleyici askıda kalmalı
- Kısa, vurucu, ritmik cümleler — TikTok/Reels formatına uygun
- Kapanışta MUTLAKA yoruma davet et

HASSAS İÇERİK KURALI (KRİTİK):
- Tecavüz, cinsel saldırı, cinsel istismar gibi kelimeleri ASLA doğrudan yazma.
- Bunların yerine KAPALICI ifadeler kullan:
  "cinsel saldırı" → "C.S. olayı" veya "cinsel nitelikli saldırı iddiası"
  "tecavüz" → "T. olayı" veya "cinsel şiddet"
  "cinsel istismar" → "istismar olayı"
  "çıplak" → "kıyafetsiz halde"
- Detay verme, sadece olayın varlığını belirt: "T. olayının yaşanmadığı belirtildi" gibi.
- Bu kural hem narration hem de scene text alanları için geçerlidir.

## ADIM 2: SAHNE BÖLME
- narration metnini 6–10 sahneye böl.
- Her sahnenin "text" alanı = narration metninin ARDIŞIK bir dilimi (kelimesi kelimesine aynı).
- Tüm sahneler sırayla birleştirildiğinde narration TAM OLARAK oluşmalı. Eksik veya fazla kelime OLMAMALI.
- Her sahne 2-4 cümle; tek cümlelik sahneler YAPMA.

## ADIM 3: GÖRSEL PROMPTLAR (image_prompt)
image_prompt (İngilizce) — OpenAI görsel güvenlik kurallarına UYMALI:
- Yasak: yaralanma, kan, çıplaklık, bağlı insan, infaz, işkence, ölü beden, silahın insana yönelmesi.
- Yasak: "dark foggy forest", "horror", "gore", generic atmosfer görseli.
- Zorunlu: DİJİTAL İLLÜSTRASYON / ANİMASYON BELGESELİ stili — stilize çizim, dramatik ışık, zengin renkler.
- KRİTİK: Her sahnenin görseli O SAHNEDE ANLATILAN OLAYI DOĞRUDAN RESMETMELİ.
- Şiddet metaforla: uzak silüetler, gölgeler, sembolik objeler, belge/arşiv yakın çekimi.
- İnsanlar çizilebilir: uzaktan silüet, yüz detaysız, stilize. Yakın yüz ifadesi YASAK.
- Yazı, logo, watermark YASAK.

motion: zoom_in, zoom_out, pan_left, pan_right; sahneler arası çeşitlendir.
Sahne duration: 5.0–10.0 sn; toplam süre hedefe yakın (±10 sn).

JSON şekli:
{"narration": "Tam akıcı anlatım metni burada...", "scenes": [{"scene_id": 1, "duration": 8.0, "text": "narration'ın bu sahneye düşen dilimi", "image_prompt": "English ...", "motion": "zoom_in"}, ...]}"""


def _fetch_case_text(url: str) -> tuple[str, str]:
    """URL'den vaka sayfasını çek, temiz metin olarak döndür.

    Returns:
        (title, body_text) — body_text en fazla 7000 karakter.
    """
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text[:7000]


def _user_message_vaka(topic: TopicConfig, case_text: str) -> str:
    sec = topic.video_duration_seconds
    min_words = max(130, int(sec * 2.3))
    max_words = max(180, int(sec * 2.8))
    return f"""Vaka İçeriği (web sayfasından çekildi):
{case_text}

---
Çıktı dili (narration ve text alanları): {topic.language}
Ton: gerçek suç belgeseli, dedektif anlatımı
Hedef konuşma süresi: ~{sec} saniye.
narration EN AZ {min_words}, EN FAZLA {max_words} kelime olmalı.
Toplam sahne duration toplamı {sec} saniyeye yakın olsun.

Tek JSON nesnesi döndür."""


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_openai_vaka(
    *, api_key: str, model: str, topic: TopicConfig, case_text: str
) -> ScenesLLMResponse:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": VAKA_NARRATION_SYSTEM},
            {"role": "user", "content": _user_message_vaka(topic, case_text)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    return ScenesLLMResponse.model_validate(data)


def write_vaka_script_and_scenes(
    *,
    topic: TopicConfig,
    output_base: Path,
    api_key: str,
    model: str,
    vaka_url: str,
) -> list[Scene]:
    """Verilen URL'den vaka detayını çekip dedektif tarzı script.txt + topic_scenes.json yazar."""
    logger.info("Vaka sayfası çekiliyor: %s", vaka_url)
    page_title, case_text = _fetch_case_text(vaka_url)
    if page_title and not topic.topic_name:
        logger.info("Vaka başlığı URL'den alındı: %s", page_title)

    logger.info("Vaka metni çekildi (%d karakter), senaryo üretiliyor...", len(case_text))
    parsed = _call_openai_vaka(api_key=api_key, model=model, topic=topic, case_text=case_text)

    # Hassas içerik filtresi — narration ve scene text'lere uygula
    if parsed.narration:
        parsed.narration = _sanitize_sensitive_content(parsed.narration)
    sanitized_scenes: list[Scene] = []
    for s in parsed.scenes:
        new_text = _sanitize_sensitive_content(s.text) if s.text else s.text
        sanitized_scenes.append(s.model_copy(update={"text": new_text}))
    parsed.scenes = sanitized_scenes

    scenes = normalize_scenes(parsed.scenes)

    script_dir = output_base / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)

    narration = (parsed.narration or "").strip()
    if not narration:
        narration = " ".join(s.text.strip() for s in scenes if s.text.strip())

    script_path = script_dir / "script.txt"
    script_path.write_text(
        "# ChronicleX — Vaka (URL → dedektif anlatım + sahne görselleri)\n\n"
        + narration
        + "\n",
        encoding="utf-8",
    )

    from modules.scripting.topic_narration import topic_scenes_json_path

    ts_path = topic_scenes_json_path(output_base)
    ts_path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Vaka senaryosu yazıldı: %s sahne, script.txt + topic_scenes.json",
        len(scenes),
    )
    return scenes
