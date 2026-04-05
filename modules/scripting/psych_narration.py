"""Psikoloji / Dark Psychology modu: interaktif konu seçimi + script üretimi."""

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

# ── Konu Önerisi ──

TOPIC_SUGGEST_SYSTEM = """Sen dünyanın en iyi sosyal medya içerik stratejistisin.
TikTok / Reels için psikoloji ve dark psychology konularında viral video fikirleri üretiyorsun.

Kullanıcıya TAM 3 konu önerisi ver. Her öneri:
- Pratik ve uygulanabilir olmalı (izleyici "bunu hayatımda kullanırım" demeli)
- Spesifik olmalı (genel "psikoloji" değil, somut bir teknik/fenomen/taktik)
- Hook potansiyeli yüksek olmalı (ilk cümle merak uyandırmalı)

Konular şu alanlardan gelebilir (sınırlı değil):
- Dark psychology, manipülasyon teknikleri, ikna yöntemleri
- Beden dili okuma, mikro ifadeler, yalan tespiti
- Sosyal mühendislik, NLP teknikleri
- Bilişsel çarpıtmalar, karar verme psikolojisi
- Narsisizm, Makyavelizm, psikopati (karanlık üçlü)
- Zihin oyunları, psikolojik savaş taktikleri
- İkna ve etkileme psikolojisi (Cialdini vb.)
- Duygusal zeka, empati, karşı manipülasyon
- Davranışsal ekonomi, seçim mimarisi
- Bilinçaltı etkileme, priming, anchoring
- Kalabalık psikolojisi, grup dinamikleri
- Hayatta kalma psikolojisi, stres altında karar verme

Her öneri farklı bir alandan olsun. Tekrar etme.

Yanıtın YALNIZCA geçerli JSON olsun:
{"suggestions": [{"title": "Kısa başlık", "hook": "Bu konuyla videonun ilk cümlesi ne olabilir", "why_viral": "Neden viral olur — 1 cümle"}, ...]}"""


def suggest_psych_topics(*, api_key: str, model: str) -> list[dict[str, str]]:
    """OpenAI'dan 3 psikoloji konu önerisi al."""
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TOPIC_SUGGEST_SYSTEM},
            {"role": "user", "content": "Bana 3 tane viral psikoloji / dark psychology video konusu öner."},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    return data.get("suggestions", [])


def interactive_topic_select(*, api_key: str, model: str) -> str:
    """Terminal'de 3 konu önerisi göster, kullanıcının seçim yapmasını bekle."""
    suggestions = suggest_psych_topics(api_key=api_key, model=model)

    print("\n" + "=" * 60)
    print("  PSYCHOLOGY / DARK PSYCHOLOGY — Konu Seçimi")
    print("=" * 60)

    for i, s in enumerate(suggestions, 1):
        print(f"\n  [{i}] {s.get('title', '?')}")
        print(f"      Hook: {s.get('hook', '')}")
        print(f"      Neden viral: {s.get('why_viral', '')}")

    print(f"\n  [4] Kendi konumu yazacağım")
    print("=" * 60)

    while True:
        choice = input("\n  Seçimin (1/2/3/4): ").strip()
        if choice in ("1", "2", "3"):
            idx = int(choice) - 1
            if idx < len(suggestions):
                selected = suggestions[idx]["title"]
                print(f"\n  Seçildi: {selected}")
                return selected
        elif choice == "4":
            custom = input("  Konunu yaz: ").strip()
            if custom:
                print(f"\n  Seçildi: {custom}")
                return custom
            print("  Boş konu giremezsin, tekrar dene.")
        else:
            print("  Geçersiz seçim, tekrar dene.")


# ── Script Üretimi ──

PSYCH_NARRATION_SYSTEM = """Sen TikTok / Reels için psikoloji ve dark psychology içerik üreticisisin.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: TAM ANLATIM METNİ (narration)

AMAÇ: İzleyici videoyu izledikten sonra öğrendiği teknikleri GERÇEK HAYATTA KULLANABİLMELİ.
Bilgi değil, SİLAH veriyorsun. İzleyici "bunu bilmem lazımdı" demeli.

YAPI:
1. HOOK (ilk cümle): Doğrudan somut bir durumla aç. İzleyiciyi kendi hayatında yakaladığı bir ana sok.
   DOĞRU: "Karşındaki kişi konuşurken burnunu kaşıyorsa, büyük ihtimalle yalan söylüyor."
   DOĞRU: "Bir manipülatör sana ilk olarak iltifat eder. Sonra yavaşça sınırlarını test etmeye başlar."
   YASAK: "Psikoloji dünyasında ilginç bir gerçek var..." / "Biliyor muydunuz..."
2. TEKNİKLER: Her tekniği somut, adım adım anlat. İzleyici direkt uygulayabilmeli.
   - Tekniğin adını ver (varsa bilimsel/popüler adı)
   - Nasıl çalıştığını 1-2 cümlede açıkla
   - Gerçek hayat örneği ver (iş, ilişki, sosyal ortam)
   - Karşı hamleyi/savunmayı da söyle (izleyici hem saldırı hem savunmayı öğrenmeli)
3. KAPANIŞ: Somut bir CTA — "Hangisini yaşadın? Yoruma yaz." veya "Bunu bilen birini etiketle."

KURALLAR:
- Minimum 3 somut teknik/bilgi öğret. İzleyici videoyu bitirdiğinde silahlanmış olmalı.
- Felsefe ve metafor KESİNLİKLE YASAK. Her cümle somut ve uygulanabilir olmalı.
  YASAK: "İnsan zihni karmaşık bir evrendir", "Psikoloji bize kendimizi keşfetmeyi öğretir"
  DOĞRU: "Birisi seninle konuşurken ayaklarını sana doğru çeviriyorsa, seni dinliyor. Kapıya doğruysa, gitmek istiyor."
- Kısa, vurucu, ritmik cümleler — TikTok formatı.
- Akademik jargon kullanabilirsin AMA her terimi hemen açıkla.
- Liste formatı güçlü: "İlk teknik...", "İkinci olarak...", "Son ve en tehlikelisi..."
- Ton: güvenilir ama biraz tehlikeli. Yasaklanmış bilgiyi paylaşıyormuş gibi.
- Kapanışta felsefe YAPMA. Son cümle de somut olsun veya güçlü bir CTA.

## ADIM 2: SAHNE BÖLME
- narration metnini 6–10 sahneye böl.
- Her sahnenin "text" alanı = narration metninin ARDIŞIK bir dilimi. Kelimesi kelimesine aynı.
- Tüm sahne text'leri birleştirildiğinde narration TAM OLARAK oluşmalı. Eksik veya fazla kelime OLMAMALI.
- Her sahne 2-4 cümle.

## ADIM 3: GÖRSEL PROMPTLAR (image_prompt)
image_prompt (İngilizce) — stilize dijital illüstrasyon:
- O sahnedeki tekniği/kavramı görselleştiren illüstrasyon.
- Örnekler: silüet figürler, beyin/zihin görselleri, beden dili pozları, satranç taşları, ayna yansımaları.
- Yasak: gore, çıplaklık, detaylı yüz, metin/logo.
- Stil: modern, minimalist, neon renk aksan, karanlık arka plan, sinematik.

motion: zoom_in, zoom_out, pan_left, pan_right; sahneler arası çeşitlendir.
Sahne duration: 5.0–10.0 sn; toplam süre hedefe yakın (±10 sn).

JSON şekli:
{"narration": "Tam anlatım metni...", "scenes": [{"scene_id": 1, "duration": 8.0, "text": "...", "image_prompt": "English ...", "motion": "zoom_in"}, ...]}"""


def _user_message(topic: TopicConfig) -> str:
    sec = topic.video_duration_seconds
    min_words = max(130, int(sec * 2.3))
    max_words = max(180, int(sec * 2.8))
    return f"""Konu: {topic.topic_name}

Çıktı dili (narration ve text alanları): {topic.language}
Ton: {topic.tone or "güvenilir, bilgili, biraz tehlikeli, dark psychology"}

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
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PSYCH_NARRATION_SYSTEM},
            {"role": "user", "content": _user_message(topic)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    return ScenesLLMResponse.model_validate(data)


def psych_scenes_json_path(output_base: Path) -> Path:
    return output_base / "scripts" / "topic_scenes.json"


def write_psych_script_and_scenes(
    *,
    topic: TopicConfig,
    output_base: Path,
    api_key: str,
    model: str,
) -> list[Scene]:
    """Psikoloji konusu script.txt + topic_scenes.json yazar."""
    parsed = _call_openai(api_key=api_key, model=model, topic=topic)
    scenes = normalize_scenes(parsed.scenes)
    script_dir = output_base / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)

    narration = (parsed.narration or "").strip()
    if not narration:
        narration = " ".join(s.text.strip() for s in scenes if s.text.strip())

    script_path = script_dir / "script.txt"
    script_path.write_text(
        "# ChronicleX — Psikoloji / Dark Psychology\n\n" + narration + "\n",
        encoding="utf-8",
    )
    ts_path = psych_scenes_json_path(output_base)
    ts_path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Psikoloji senaryosu yazıldı: %s sahne, script.txt + topic_scenes.json", len(scenes))
    return scenes
