"""Film özeti: spoiler'sız, merak uyandıran, somut anlatım + sahne bölme."""

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

MOVIE_NARRATION_SYSTEM = """Sen TikTok / Reels için film tanıtım içeriği üreticisisin.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: FİLM ÖZETİ METNİ (narration)

AMAÇ: İzleyici filmi izlememiş. Videoyu izledikten sonra filmi merak edip izlemeye koşmalı.

KURALLAR:
- Filmin konusunu, ana karakterleri ve temel çatışmayı anlat.
- SPOILER VERME. Klimaks ve final ANLATILMAZ. Filmin ilk yarısına kadar olan olayları anlat.
- Metafor ve felsefi cümleler KESİNLİKLE YASAK.
  YASAK: "Korku aslında içimizde saklıdır", "Bu film insanlığın karanlık yüzünü sorguluyor"
  DOĞRU: "Adam uyandığında kendini boş bir odada buldu. Kapı kilitliydi ve cebinde sadece bir not vardı."
- Somut olay akışı anlat: ne oldu, kim yaptı, nerede, ne zaman.
- Anlatımı filmdeki somut bir gerilim noktasında KES ve o sahneyle ilgili merak uyandıran sorular sor.
  YASAK: "Tam bu noktada beklenmedik bir şey olur."
  DOĞRU: "Yıllardır yalnız yaşayan bu kadın, kendisini takip eden kişiyi fark etti. Ama takip eden kimdi? Ve ne istiyordu?"
  DOĞRU: "Masanın üstünde duran zarfı açtığında içinden kendi fotoğrafı çıktı. Bu fotoğrafı kim çekmiş olabilirdi?"
- Soruları filmdeki GERÇEK bir sahneye/olaya dayandır. Uydurma değil.
- "Bu filmde neler olacağını öğrenmek için izlemelisiniz" tarzında ucuz CTA YASAK.
- Anlatımın başında veya ortasında, filmden DİKKAT ÇEKİCİ bir sahne detayı ver.
  İzleyiciyi o anın içine sok — sanki o sahneyi yaşıyormuş gibi hissettir.
  YASAK: Genel gerilim cümleleri ("korkunç bir şey oldu", "beklenmedik bir olay yaşandı")
  DOĞRU: "Otopsiyi yapıyorsun, her şey temiz görünüyor — ama birden cesedin ağzından böcekler çıkmaya başlıyor."
  DOĞRU: "Aynaya bakıyorsun ama yansımandaki sen, senin yaptığını yapmıyor."
  Bu detay filmdeki GERÇEK bir sahneye dayanmalı, uydurma olmamalı.
- Arkadaş ortamında film anlatan biri gibi yaz: doğal, akıcı, heyecanlı.
- Kısa, vurucu cümleler — TikTok formatı.
- "Biliyor muydunuz" tarzı ucuz hook YASAK. Doğrudan sahneye gir.

## ADIM 2: SAHNE BÖLME
- narration metnini 6–10 sahneye böl.
- Her sahnenin "text" alanı = narration metninin ARDIŞIK bir dilimi. Kelimesi kelimesine aynı.
- Tüm sahne text'leri birleştirildiğinde narration'ı TAM oluşturmalı.
- Her sahne 2-4 cümle.

## ADIM 3: GÖRSEL PROMPTLAR (image_prompt)
image_prompt (İngilizce) — filmdeki sahneyi betimle:
- Stilize dijital illüstrasyon / sinematik art style.
- O sahnedeki somut olayı resmeden görsel: mekan, karakter silüetleri, objeler.
- Yasak: gore, çıplaklık, detaylı yüz, silah insana yönelmiş, metin/logo.
- İnsanlar: uzak silüet veya stilize figür olarak çizilebilir.

motion: zoom_in, zoom_out, pan_left, pan_right; sahneler arası çeşitlendir.
Sahne duration: 5.0–10.0 sn; toplam süre hedefe yakın (±10 sn).

JSON şekli:
{"narration": "Tam özet metni...", "scenes": [{"scene_id": 1, "duration": 8.0, "text": "...", "image_prompt": "English ...", "motion": "zoom_in"}, ...]}"""


def _user_message(topic: TopicConfig) -> str:
    sec = topic.video_duration_seconds
    min_words = max(100, int(sec * 2.3))
    max_words = max(150, int(sec * 2.8))
    return f"""Film adı / konu: {topic.topic_name}

Çıktı dili (narration ve text alanları): {topic.language}
Ton: heyecanlı, merak uyandıran, arkadaşça

Hedef konuşma süresi: yaklaşık {sec} saniye.
narration metni EN AZ {min_words}, EN FAZLA {max_words} kelime olmalı.
Toplam sahne duration toplamı {sec} saniyeye yakın olsun.

Tek JSON nesnesi döndür."""


@retry(
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_openai(*, api_key: str, model: str, topic: TopicConfig) -> ScenesLLMResponse:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MOVIE_NARRATION_SYSTEM},
            {"role": "user", "content": _user_message(topic)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    return ScenesLLMResponse.model_validate(data)


def movie_scenes_json_path(output_base: Path) -> Path:
    return output_base / "scripts" / "topic_scenes.json"


def write_movie_script_and_scenes(
    *,
    topic: TopicConfig,
    output_base: Path,
    api_key: str,
    model: str,
) -> list[Scene]:
    """Film özeti script.txt + topic_scenes.json yazar."""
    parsed = _call_openai(api_key=api_key, model=model, topic=topic)
    scenes = normalize_scenes(parsed.scenes)
    script_dir = output_base / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)

    narration = (parsed.narration or "").strip()
    if not narration:
        narration = " ".join(s.text.strip() for s in scenes if s.text.strip())

    script_path = script_dir / "script.txt"
    script_path.write_text(
        "# ChronicleX — Film Özeti (spoiler'sız)\n\n" + narration + "\n",
        encoding="utf-8",
    )
    ts_path = movie_scenes_json_path(output_base)
    ts_path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Film özeti yazıldı: %s sahne, script.txt + topic_scenes.json", len(scenes))
    return scenes
