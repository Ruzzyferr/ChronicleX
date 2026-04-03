"""Konu başlığından OpenAI ile anlatım metni + sahne başına DALL·E prompt (JSON)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from core.media_models import Scene, ScenesLLMResponse
from core.models import TopicConfig
from modules.scripting.scene_generator import normalize_scenes

logger = logging.getLogger(__name__)

TOPIC_NARRATION_SYSTEM = """Sen dikey tarih belgeseli (Shorts / Reels) için viral içerik üreticisisin.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: TAM ANLATIM METNİ (narration)
- Önce "narration" alanına TAM, AKICI, KESİNTİSİZ bir anlatım metni yaz. Bu metin doğrudan seslendirilecek.
- Bir hikaye anlatıyormuş gibi yaz — başı, ortası, sonu olan TEK BİR AKIŞ.
- İlk cümle MUTLAKA güçlü bir hook olsun: izleyiciyi ilk saniyede yakalayan, şok edici veya merak uyandıran bir açılış.
- Kısa, vurucu, ritmik cümleler — TikTok/Reels formatına uygun.
- Her cümle bir öncekiyle BAĞLANTILI olsun. Geçiş kelimeleri kullan. Hikaye aksın.
- Akış: çarpıcı hook → bağlam → kronoloji/olaylar → sonuç/miras → güçlü kapanış.
- Kapanış da akılda kalıcı olsun — düşündüren veya şaşırtan bir son cümle.
- Konuyu TEK somut odakta topla; doğrulanabilir, eğitici ama büyüleyici.

## ADIM 2: SAHNE BÖLME
- narration metnini 6–10 sahneye böl.
- Her sahnenin "text" alanı = narration metninin ARDIŞIK bir dilimi. Kelimesi kelimesine aynı olmalı.
- Tüm sahne text'leri sırayla birleştirildiğinde narration metnini TAM OLARAK oluşturmalı. Eksik veya fazla kelime OLMAMALI.
- Her sahne yeterince uzun olsun (2-4 cümle). Çok kısa tek cümlelik sahneler YAPMA.

## ADIM 3: GÖRSEL PROMPTLAR (image_prompt)
image_prompt (İngilizce) — OpenAI görsel API güvenlik kurallarına UYMALI:
- Yasak: yaralanma, kan, çıplaklık, bağlı insan, infaz, işkence anı, acı çeken yüz/vücut, silahın insana yönelmesi, ölü beden, cinsel şiddet, ayrıntılı şiddet.
- Yasak: "dark foggy forest", "horror", "gore", "blood", "terrified", generic sisli orman.
- Görselde yazı, logo, watermark isteme.
- Zorunlu tarz: DİJİTAL İLLÜSTRASYON / ANİMASYON BELGESELİ stili — stilize çizim, dramatik ışık, zengin doygun renkler, yüksek prodüksiyon.
- KRİTİK: Her sahnenin görseli O SAHNEDE ANLATILAN OLAYI DOĞRUDAN RESMETMELİ. Generic atmosfer görseli YAPMA.
- Şiddeti METAFOR veya BAĞLAM ile anlat: uzak silüetler, gölgeler, sembolik objeler, belge/ferman yakın çekimi, mekân atmosferi.
- İnsanlar çizilebilir: uzaktan silüet, yüz detaysız, stilize/animasyon tarzında. Yakın çekim yüz ifadesi YASAK.

motion: zoom_in, zoom_out, pan_left, pan_right; sahneler arası çeşitlendir.
Sahne duration: 5.0–10.0 sn; toplam süre hedefe yakın (±10 sn).

JSON şekli:
{"narration": "Tam akıcı anlatım metni burada...", "scenes": [{"scene_id": 1, "duration": 8.0, "text": "narration'ın bu sahneye düşen dilimi", "image_prompt": "English ...", "motion": "zoom_in"}, ...]}"""


def _user_message(topic: TopicConfig) -> str:
    sec = topic.video_duration_seconds
    min_words = max(100, int(sec * 2.3))
    max_words = max(150, int(sec * 2.8))
    return f"""Konu başlığı / istek: {topic.topic_name}

Çıktı dili (narration ve text alanları): {topic.language}
Ton: {topic.tone or "ciddi belgesel"}

Hedef konuşma süresi: yaklaşık {sec} saniye.
narration metni EN AZ {min_words}, EN FAZLA {max_words} kelime olmalı. Bu çok önemli — kısa yazarsan video çok kısa olur.
Toplam sahne duration toplamı {sec} saniyeye yakın olsun.

Tek JSON nesnesi döndür."""


def topic_scenes_json_path(output_base: Path) -> Path:
    return output_base / "scripts" / "topic_scenes.json"


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_openai(*, api_key: str, model: str, topic: TopicConfig) -> ScenesLLMResponse:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TOPIC_NARRATION_SYSTEM},
            {"role": "user", "content": _user_message(topic)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    return ScenesLLMResponse.model_validate(data)


def write_topic_script_and_scenes(
    *,
    topic: TopicConfig,
    output_base: Path,
    api_key: str,
    model: str,
) -> list[Scene]:
    """script.txt + topic_scenes.json yazar; dönen sahne listesi render tarafında kullanılır."""
    parsed = _call_openai(api_key=api_key, model=model, topic=topic)
    scenes = normalize_scenes(parsed.scenes)
    script_dir = output_base / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    # narration alanı varsa onu kullan (tam akıcı metin), yoksa sahne textlerini birleştir
    narration = (parsed.narration or "").strip()
    if not narration:
        narration = " ".join(s.text.strip() for s in scenes if s.text.strip())
    script_path = script_dir / "script.txt"
    script_path.write_text(
        "# ChronicleX — OpenAI (konu → anlatım + sahne görselleri)\n\n" + narration + "\n",
        encoding="utf-8",
    )
    ts_path = topic_scenes_json_path(output_base)
    ts_path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Konu anlatımı yazıldı: %s sahne, script.txt + topic_scenes.json",
        len(scenes),
    )
    return scenes
