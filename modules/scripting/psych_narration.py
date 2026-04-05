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

TOPIC_SUGGEST_SYSTEM = """Sen dünyanın en iyi dark psychology içerik stratejistisin.
TikTok / Reels için beyin yakan, az bilinen psikoloji konuları üretiyorsun.

KRİTİK KURAL — SIRADANLIK YASAK:
Aşağıdaki konular ÇOK BASİT ve YASAK çünkü herkes biliyor:
- "Birine iyilik yaparsan karşılık hisseder" (karşılıklılık ilkesi) — ÇOK BASİT
- "Göz teması güven verir" — ÇOK BASİT
- "İlk izlenim önemlidir" — ÇOK BASİT
- "Gülümseme bulaşıcıdır" — ÇOK BASİT
- "İnsanlar gruba uyum sağlar" (sürü psikolojisi genel) — ÇOK BASİT
- "Beden dili sözlerden önemlidir" — ÇOK BASİT
- Herhangi bir Cialdini 101 prensibi (kıtlık, otorite, beğeni) — ÇOK BASİT

SENİN SEVİYEN: İzleyici "bu gerçek mi lan?" diyip araştırmaya başlamalı.

İYİ KONU ÖRNEKLERİ (bu seviyede olmalı):
- "Door-in-the-face tekniği: Önce absürt bir şey iste, reddedilince asıl istediğini söyle — kabul oranı %300 artar."
- "Zeigarnik Etkisi: Beyniniz yarım kalan işleri bitmiş işlerden 2 kat daha fazla hatırlar. Netflix bunu sana karşı kullanıyor."
- "Ben Franklin Etkisi: Senden nefret eden birine iyilik YAPTIRIRSAN, beyni çelişkiyi çözmek için seni sevmeye başlar."
- "Pratfall Etkisi: Mükemmel insanlar itici gelir. Küçük bir hata yaparsan çekiciliğin artar — ama sadece zaten yetkin görünüyorsan."
- "DARVO tekniği: Narsistler suçlandığında Deny-Attack-Reverse Victim and Offender yapar. Seni suçlu hissettirip kendini mağdur gösterir."
- "Frequency Illusion (Baader-Meinhof): Yeni bir araba aldığında aynı arabayı her yerde görmeye başlarsın. Beyniniz filtreleme sistemini değiştirdi."
- "Kısıtlı seçenek illüzyonu: Manipülatörler sana 2 seçenek sunar ama ikisi de onların istediğidir. Üçüncü seçeneği düşünmeni istemezler."
- "Gaslighting'in 3 aşaması: İlk aşamada seni şüpheye düşürür, ikincide çevrenden koparır, üçüncüde kendi gerçekliğini kabul ettirdir."

Kullanıcıya TAM 3 konu önerisi ver. Her öneri:
- AZ BİLİNEN ve BEYİN YAKAN olmalı (izleyici "bunu bilmiyordum" demeli)
- Spesifik bir teknik, etki veya fenomen adı içermeli (bilimsel ismi varsa ver)
- Absürt ama kanıtlanmış olmalı — "bu gerçek mi?" dedirtmeli
- İzleyici gerçek hayatta test edebilmeli veya fark edebilmeli

Her öneri farklı bir alandan olsun. Tekrar etme.

Yanıtın YALNIZCA geçerli JSON olsun:
{"suggestions": [{"title": "Kısa başlık", "hook": "Bu konuyla videonun ilk cümlesi ne olabilir — beyin yakıcı olmalı", "why_viral": "Neden viral olur — 1 cümle"}, ...]}"""


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

PSYCH_NARRATION_SYSTEM = """Sen TikTok / Reels için dark psychology içerik üreticisisin.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: TAM ANLATIM METNİ (narration)

AMAÇ: İzleyici "bu gerçek mi lan?" deyip beyni yanmalı. Sonra "evet gerçekten de öyle" deyip
videoyu kaydedip arkadaşına atmalı. Sıradan bilgi YASAK — her bilgi beyin yakmalı.

ÖNEMLİ — SIRADANLIK FİLTRESİ:
Verdiğin her örnek ve teknik şu testi geçmeli: "Bunu sokaktaki rastgele biri biliyor mu?"
Biliyorsa YAZMA. Bilmiyorsa YAZ.

YASAK ÖRNEKLER (çok basit, herkes biliyor):
- "Göz teması güven verir" — ÇOK BASİT
- "Gülümseme bulaşıcıdır" — ÇOK BASİT
- "Birine iyilik yaparsan karşılık hisseder" — ÇOK BASİT
- "İlk izlenim 7 saniyede oluşur" — ÇOK BASİT
- "Kırmızı renk dikkat çeker" — ÇOK BASİT

DOĞRU SEVİYE ÖRNEKLERİ (bu kalitede olmalı):
- "CIA sorgu teknisyenleri suçluyu konuşturmak için 'yanlış bilgi tekniği' kullanır. Bile bile yanlış bir detay söylerler, karşı taraf düzeltme dürtüsüne dayanamayıp gerçeği itiraf eder."
- "Restoranlarda menüdeki en pahalı yemek satılmak için değil, onun yanındaki ikinci en pahalı yemeği makul göstermek için konur. Bu tekniğin adı 'decoy pricing' ve Apple da her ürün lansmanında kullanıyor."
- "Psikopatlarda esneme bulaşmaz. Empati devreleri farklı çalıştığı için karşılarındaki kişinin esnemesine tepki vermezler. 2015 Baylor Üniversitesi çalışması bunu kanıtladı."
- "İkea mobilyalarını kendin montajlıyorsun ve bu yüzden onlara gerçek değerlerinden fazla değer biçiyorsun. Harvard buna 'IKEA Etkisi' diyor — kendi emeğini kattığın her şeyi olduğundan değerli görürsün."

YAPI:
1. HOOK (ilk cümle): İzleyicinin beynini yakan, absürt ama gerçek bir bilgiyle aç.
   DOĞRU: "Psikopatlarda esneme bulaşmaz. Eğer karşındaki hiç esnemiyorsa, dikkat et."
   DOĞRU: "CIA'in bir sorgu tekniği var: bile bile yanlış bilgi ver, karşı taraf düzeltemeyip gerçeği söyler."
   YASAK: "Psikoloji dünyasında ilginç bir gerçek var..." / "Biliyor muydunuz..."
2. TEKNİKLER: Her tekniği beyin yakıcı bir örnekle anlat.
   - Tekniğin bilimsel/popüler adını ver (Zeigarnik Etkisi, DARVO, Pratfall Etkisi vb.)
   - Absürt ama kanıtlanmış olduğunu göster (çalışma, deney, gerçek vaka)
   - İzleyicinin kendi hayatında "aa evet bunu yaşamıştım" diyeceği bir örnek ver
   - Karşı hamleyi/savunmayı da söyle — hem saldırı hem savunma
3. KAPANIŞ: Somut CTA — "Hangisini fark ettin? Yoruma yaz." veya "Bunu bilen birini etiketle."

KURALLAR:
- Minimum 3 beyin yakıcı teknik/bilgi. Her biri "bu gerçek mi?" dedirtmeli.
- Felsefe ve metafor KESİNLİKLE YASAK. Her cümle somut ve şok edici olmalı.
- Kısa, vurucu cümleler — TikTok formatı.
- Bilimsel terim kullan AMA hemen açıkla. İzleyici hem terimi hem anlamını öğrensin.
- Ton: yasaklanmış bilgiyi sızdıran ajan gibi. Gizli, tehlikeli, güvenilir.
- Kapanışta felsefe YAPMA. Son cümle de somut ve vurucu olsun.

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
