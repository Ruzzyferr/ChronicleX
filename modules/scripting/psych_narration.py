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

## HOOK YAZIM KURALI (ÇOK ÖNEMLİ)
Hook = videonun ilk cümlesi. Kısa, somut, şok edici bir GERÇEK olmalı.
- Maksimum 15 kelime.
- Soru sorma, doğrudan bilgiyi patlat.
- DOĞRU: "Psikopatlarda esneme bulaşmaz."
- DOĞRU: "Netflix yarım bıraktığın diziyi önce gösterir çünkü beyniniz yarım işleri unutamaz."
- DOĞRU: "Apple her lansmanında sana 3 seçenek sunar ama ortadakini satın alman için tasarlanmıştır."
- YANLIŞ: "Neden en az bilgiye sahip olanlar kendilerini en yetkin zanneder?" (soru sorma)
- YANLIŞ: "Bu ilginç durum sosyal hayatı nasıl etkiliyor?" (soru sorma, belirsiz)
- YANLIŞ: "Eğer birine ismini doğru söylersen onu etkileyebilirsin, bu bir manipülasyon değil mi?" (uzun, soru)

Yanıtın YALNIZCA geçerli JSON olsun:
{"suggestions": [{"title": "Kısa başlık", "hook": "Kısa, somut, şok edici bir gerçek cümlesi.", "why_viral": "Neden viral olur — 1 cümle"}, ...]}"""


PSYCH_MODEL = "gpt-4o"  # gpt-4o-mini kalitesi yeterli değil, gpt-4o ile beyin yakan içerik


def suggest_psych_topics(*, api_key: str, model: str) -> list[dict[str, str]]:
    """OpenAI'dan 3 psikoloji konu önerisi al."""
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=PSYCH_MODEL,
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

PSYCH_NARRATION_SYSTEM = """Sen Türkiye'de yaşayan, Türk gençliğini iyi tanıyan bir dark psychology içerik üreticisisin.
Yanıtın YALNIZCA geçerli JSON olsun (başka metin yok).

## ADIM 1: TAM ANLATIM METNİ (narration)

AMAÇ: Türk genci "abi bu gerçek mi ya?" deyip videoyu kaydedip grubuna atmalı.

## HEDEF KİTLE: TÜRKİYE GENÇLİĞİ

Sen Türkiye'de büyümüş, Türk aile yapısını, eğitim sistemini, sokak kültürünü bilen birisin.
Örneklerin TÜRK GENÇLERİNİN GÜNLÜK HAYATINDAN olmalı. Batılı, uzak örnekler YASAK.

TÜRKİYE'YE ÖZEL ÖRNEKLER KULLAN:
- AVM kültürü, BİM/A101/ŞOK indirimleri, market taktikleri
- Türk aile yapısı: "annen sana seçenek sunuyor ama ikisi de onun istediği"
- Üniversite sistemi: YKS, sıralama baskısı, dershane, tercih dönemi
- Sosyal medya: Türk Twitter/X, Instagram keşfet, TikTok Türkiye trendleri
- İş hayatı: staj, asgari ücret, patron-çalışan ilişkisi, mülakat
- Arkadaş grupları: mahalle, okul, askerlik, cemaat baskısı
- Türk dizileri, reklamları, markaları (Trendyol, Getir, Hepsiburada)
- Gündem: ekonomi, döviz, kira, enflasyon — gençlerin gerçek derdi

YASAK ÖRNEKLER (Türk genci bağ kuramaz):
- "Harvard'da yapılan bir araştırma..." — UZAK, SAHİPLENEMİYOR
- "Amerika'da bir süpermarkette..." — ALAKASIZ
- "MIT öğrencileri..." — BİZDEN DEĞİL
- "New York'ta bir kadın..." — TÜRKİYE'DE DEĞİL

DOĞRU ÖRNEKLER (Türk genci "abi ben de yaşadım" der):
- "BİM'e sadece ekmek almaya giriyorsun. 10 dakika sonra elinde 3 poşet var. Ekmek en arkada çünkü. Yürürken gördüğün her şeyi sepete atıyorsun. Tesadüf değil, taktik."
- "Annen diyor ki 'ya odanı topla ya da telefonu bırak.' İkisi de onun istediği. Üçüncü seçenek yok. Buna kısıtlı seçenek illüzyonu deniyor."
- "Trendyol'da 500 liralık ayakkabıya bakıyorsun. Yanında 1200 liralık var, üstü çizili. 500'lük birden ucuz geliyor. Bu dikoy prayzing denen şey."
- "YKS'den önce herkes 'rahat ol stres yapma' diyor. Ama stres yapma demek beyni daha çok strese sokuyor. Buna ironic process theory deniyor."

## DİL VE TON

Türk genci gibi konuş. Ağdalı, kibar, "efendim" tarzı değil. Samimi, direkt, biraz küstah.

YASAK TON:
- "Araştırmalar göstermektedir ki..." — MAKALE DEĞİL BU
- "Bu fenomen şu şekilde açıklanabilir..." — DERS DEĞİL
- "Sonuç olarak, kendinizi geliştirmek önemlidir." — VAAZ DEĞİL

DOĞRU TON:
- "Abi şimdi bunu duy."
- "Bak şimdi, patron sana iki seçenek sunuyor."
- "Sen farkında değilsin ama her gün bunu yaşıyorsun."
- "Kısacası, seni oynuyorlar ve sen alkış tutuyorsun."

KURAL: Her cümleyi yaz, sonra kendine sor: "20 yaşında bir Türk genci bunu arkadaşına böyle mi anlatır?"
Hayırsa SİL, yeniden yaz.

## İÇERİK KALİTESİ

SIRADANLIK FİLTRESİ: "Bunu sokaktaki rastgele biri biliyor mu?" Biliyorsa YAZMA.

YASAK (herkes biliyor):
- Göz teması, gülümseme, ilk izlenim, kırmızı renk, karşılıklılık ilkesi

## YAPI

1. HOOK (ilk cümle): Türk gencinin beynini yakan, kendi hayatından bir gerçekle direkt gir.
   DOĞRU: "BİM'e ekmek almaya girip 3 poşetle çıkıyorsun. Bu tesadüf değil, sana karşı kullanılan bir taktik."
   DOĞRU: "Annen sana hep iki seçenek sunar. İkisi de onun istediği. Üçüncü seçenek aklına bile gelmez."
   YASAK: "Psikoloji dünyasında ilginç bir gerçek var..." / "Biliyor muydunuz..."

2. GELİŞME: Konuyu EN AZ 2-3 FARKLI AÇIDAN anlat. Tek bilgi verip bırakma.
   - Bilimsel adını Türkçe okunuşuyla ver, hemen sokak dilinde açıkla
   - TÜRKİYE'DEN spesifik örnek ver (marka, yer, durum)
   - Gencin kendi hayatında "lan ben de yaşadım" diyeceği sahne çiz
   - Dark tarafı göster: bunu sana karşı KİM, NASIL kullanıyor
   - Her açıdan sonra şok edici bir detayla bitir

3. KAPANIŞ: Her video FARKLI kapanış. Konuya özel, Türk gencini kışkırtan.
   YASAK: "Hangisini yaşadın?", "Yoruma yaz", "Ne düşünüyorsunuz?" — HER VİDEODA AYNI
   DOĞRU: Konuya özel, tartışma başlatan, kişisel.
   Örnek: "Trendyol'dan son aldığın şeye bak. Yanındaki pahalı ürün yüzünden mi aldın? Fiyatı yoruma yaz."
   Örnek: "Annenin son 'ya şunu yap ya bunu yap' dediği anı hatırla. Üçüncü seçeneği hiç düşündün mü?"

## ÖRNEK KALİTESİ — KRİTİK

Her örnek MANTIK TESTİ + TÜRKİYE TESTİ geçmeli:
1. "Bu şaşırtıcı mı yoksa bariz mi?" — Barizse SİL.
2. "Türk genci bunu yaşıyor mu?" — Yaşamıyorsa SİL.

YASAK (mantıksız veya alakasız):
- "Biriyle yemeğe gidiyorsun ve bağ kuruyorsun" — BARIZ
- "MIT öğrencileri..." — TÜRKİYE'DE DEĞİL
- "Bir alışveriş merkezinde yere düşen biri..." — ZORLAMA

DOĞRU (şaşırtıcı + Türkiye):
- "BİM kasasının yanına çikolata koyuyor. Sırada beklerken gözün takılıyor, alıyorsun. Buna impals bayıng deniyor. Sadece BİM değil, A101, ŞOK, Migros hepsi yapıyor."
- "Dershane hocası 'bu konuyu herkes yanlış yapıyor' diyor. Sen birden dikkat kesiliyorsun. Çünkü beyin tehdit algılıyor. Buna loss aversion deniyor, kaybetme korkusu."
- "İnstagram keşfette hep aynı tarz postlar görüyorsun. Beynin buna alışıyor ve farklı düşünemez hale geliyor. Buna filtre balonu deniyor."

KURALLAR:
- Felsefe, tavsiye, "kendinizi geliştirin" KESİNLİKLE YASAK.
- Genel ifadeler YASAK: "araştırmalar gösteriyor" — KİM, NEREDE, NE ZAMAN?
- Script içinde max 1-2 soru. Soru yerine bilgiyi direkt patlat.
- Kısa, vurucu cümleler. Max 15-20 kelime per cümle.
- "Bu kadar basit" gibi küçümseme YASAK.
- Ton: mahallede takılırken kanka'na beyin yakan bilgi anlatan adam.
- İçerik SIĞ olmasın: en az 2-3 farklı açı (günlük hayat, dark kullanım, savunma).

## YAZIM VE NOKTALAMA — TTS İÇİN KRİTİK

Bu metin seslendirilecek (TTS). Doğru okunması için:

1. NOKTALAMA: Her cümle nokta/ünlem/soru ile bitmeli. Virgüller doğru yerde.
   Uzun cümleleri kısa cümlelere böl — TTS uzun cümlelerde garip duraklamalar yapıyor.

2. İNGİLİZCE TERİMLER: SADECE Türkçe okunuşuyla yaz. Parantez içi İngilizce YASAK.
   TTS her şeyi okuyor, İngilizce yazarsan yanlış okur veya iki kere okur.
   - "Placebo" → "Plasebo"
   - "Decoy" → "Dikoy"
   - "Gaslighting" → "Geslayting"
   - "Door-in-the-face" → "Dor in dı feys"
   - "Anchoring" → "Enkoring"
   - "Framing" → "Freyming"
   - "Priming" → "Prayming"
   - "Bystander" → "Baystender"
   - "Impulse buying" → "İmpals bayıng"
   - "Loss aversion" → "Los averjiın"
   - "Filter bubble" → "Filtre balonu" (Türkçe çevirisi varsa onu kullan)
   YASAK: "Plasebo (Placebo) etkisi" — TTS iki kere okur
   DOĞRU: "Plasebo etkisi"

3. CÜMLE UZUNLUĞU: Max 15-20 kelime. Uzunsa ikiye böl.

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
        model=PSYCH_MODEL,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PSYCH_NARRATION_SYSTEM},
            {"role": "user", "content": _user_message(topic)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(content)
    return ScenesLLMResponse.model_validate(data)


# ── Sosyal Medya Metadata ──

SOCIAL_METADATA_SYSTEM = """Sen 2026'da çalışan, güncel trendleri bilen bir sosyal medya uzmanısın.
Verilen psikoloji/dark psychology video konusu ve script'i için TikTok, Instagram ve YouTube için AYRI AYRI içerik üreteceksin.

## GENEL KURALLAR

- Tüm hook'lar ve açıklamalar TAM CÜMLELER olmalı. Yarım bırakılmış cümle YASAK.
- Hook'larda SORU SORMA. Direkt şok edici bir bilgi/iddia yaz.
- Emoji kullanımı: TikTok'ta minimal (0-1), Instagram'da orta (2-3), YouTube'da yok.
- DİL: Türkçe. Hashtagler hem Türkçe hem İngilizce karışık.

## PLATFORM KURALLARI

### TikTok
- Hook: Max 10 kelime, şok edici, soru YASAK. "Beynin seni kandırıyor ve sen farkında bile değilsin."
- Başlık: Kısa, merak uyandıran, emoji max 1
- Açıklama: Max 2 cümle, vurucu
- Hashtagler: 5-8 adet. 2026 TikTok trendleri. #fyp #foryou #keşfet GİBİ ÖLÜ hashtagler YASAK.
  DOĞRU: #darkpsikoloji #beyinhack #psikolojikgerçekler #bilimkurgu #zihinoyunları
- En iyi saatler: Hafta içi 19:00-21:00, hafta sonu 14:00-16:00

### Instagram Reels
- Hook: Max 15 kelime, merak uyandıran bilgi
- Başlık: Carousel/Reels formatına uygun
- Açıklama: 3-5 cümle, hikaye anlatır gibi, CTA içermeli
- Hashtagler: 10-15 adet. Niş + orta büyüklük karışımı.
  YASAK: #keşfet #instagram #instagood #motivation #love — ÖLMÜŞ hashtagler
  DOĞRU: #psikolojibilimi #darkpsychology #manipülasyon #zihinokuma #bilimselgerçekler
- En iyi saatler: Hafta içi 11:00-13:00 veya 19:00-21:00

### YouTube Shorts
- Hook: SEO uyumlu, arama yapılabilir
- Başlık: Max 60 karakter, anahtar kelime içermeli, clickbait ama gerçek
- Açıklama: 3-5 cümle, anahtar kelime yoğun, izleyiciyi kanala yönlendir
- Hashtagler: 5-8 adet, arama odaklı
  DOĞRU: #psikoloji #darkpsychology #shorts #bilim #beyin
- En iyi saatler: Hafta içi 14:00-16:00, hafta sonu 10:00-12:00

## YASAK HASHTAGLER (ölü, spam, 2020 kalıntısı — KULLANMA):
#keşfet #fyp #foryou #foryoupage #viral #trending #instagood #love #motivation
#kişiselgelişim #motivasyon #başarı #hedef #hayat #günaydın #instadaily

best_time formatı: "Pazartesi/Çarşamba/Cuma 19:00-21:00" gibi gün + saat aralığı.

Yanıtın YALNIZCA geçerli JSON olsun:
{
  "tiktok": {
    "hook": "...",
    "title": "...",
    "description": "...",
    "hashtags": ["#tag1", "#tag2", ...],
    "best_time": "Gün + saat aralığı"
  },
  "instagram": {
    "hook": "...",
    "title": "...",
    "description": "...",
    "hashtags": ["#tag1", "#tag2", ...],
    "best_time": "Gün + saat aralığı"
  },
  "youtube": {
    "hook": "...",
    "title": "...",
    "description": "...",
    "hashtags": ["#tag1", "#tag2", ...],
    "best_time": "Gün + saat aralığı"
  }
}"""


def generate_social_metadata(*, topic_name: str, narration: str, api_key: str) -> dict:
    """AI ile 3 platform için sosyal medya metadata üret."""
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=PSYCH_MODEL,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SOCIAL_METADATA_SYSTEM},
            {"role": "user", "content": f"Konu: {topic_name}\n\nScript:\n{narration}"},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)


def _write_social_txt_files(social: dict, script_dir: Path) -> None:
    """Her platform için ayrı txt dosyası yaz."""
    for platform in ("tiktok", "instagram", "youtube"):
        data = social.get(platform, {})
        if not data:
            continue
        lines = [
            f"=== {platform.upper()} ===",
            "",
            f"HOOK: {data.get('hook', '')}",
            "",
            f"BAŞLIK: {data.get('title', '')}",
            "",
            "AÇIKLAMA:",
            data.get("description", ""),
            "",
            "HASHTAGLER:",
            " ".join(data.get("hashtags", [])),
            "",
            f"EN İYİ PAYLAŞIM SAATİ: {data.get('best_time', '')}",
            "",
        ]
        path = script_dir / f"{platform}.txt"
        path.write_text("\n".join(lines), encoding="utf-8")


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

    # Sosyal medya metadata üret (txt dosyaları)
    social = generate_social_metadata(
        topic_name=topic.topic_name,
        narration=narration,
        api_key=api_key,
    )
    _write_social_txt_files(social, script_dir)
    logger.info("Sosyal medya metadata yazıldı: tiktok.txt, instagram.txt, youtube.txt")

    return scenes
