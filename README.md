# ChronicleX

Konu ver, video al. TikTok / YouTube Shorts / Reels icin otomatik dikey video uretim pipeline'i.

## Ne Yapar?

Komut satirindan bir konu veya URL veriyorsun, pipeline sirasiyla:

1. **Script** — OpenAI ile Turkce anlati metni + sahne plani olusturur
2. **Ses** — ElevenLabs ile seslendirme yapar
3. **Gorsel** — DALL-E / Lexica ile gorseller veya gameplay arka plan
4. **Video** — FFmpeg ile 1080x1920 dikey video uretir (altyazi dahil)

Cikti: `output/productions/<tarih>__<konu>/video/final.mp4`

---

## Kurulum

### 1. Gereksinimler

- Python 3.11+
- FFmpeg (altyazi yakma ve video birlestirme icin)
- PostgreSQL (opsiyonel, sadece topic discovery icin)

### 2. FFmpeg Kur

**Windows:**
```bash
winget install -e --id Gyan.FFmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

Kurulduktan sonra kontrol:
```bash
ffmpeg -version
```

### 3. Projeyi Kur

```bash
git clone <repo-url>
cd ChronicleX

python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. .env Ayarla

```bash
cp .env.example .env
```

`.env` dosyasini ac ve API anahtarlarini doldur:

| Degisken | Gerekli Mi | Aciklama |
|----------|-----------|----------|
| `OPENAI_API_KEY` | Evet | Script uretimi + Whisper altyazi sync |
| `ELEVENLABS_API_KEY` | Evet | Seslendirme (TTS) |
| `ELEVENLABS_VOICE_ID` | Hayir | Varsayilan ses ID (degistirmek istersen) |
| `DATABASE_URL` | Hayir | PostgreSQL (sadece discovery fazi icin) |
| `FFMPEG_PATH` | Hayir | FFmpeg PATH'te degilse tam yol |

Diger API anahtarlari (YouTube, TikTok, Instagram) sadece `--publish` kullanacaksan gerekli.

### 5. Test Et

```bash
# API cagrisi yapmadan simule et
python run.py --dry-run
```

Hata yoksa kurulum tamam.

---

## Komutlar

### Tarih / Genel Konu

```bash
# Varsayilan konu (config/topic.yaml'dan)
python run.py

# Kendi konunla
python run.py --topic "Roma Imparatorlugu'nun cokusu"
```

### Psikoloji / Dark Psychology

```bash
# Interaktif: 3 konu onerisi gelir, birini sec veya kendi konunu yaz
python run.py --psych

# Direkt konu ver (secim ekrani atlanir)
python run.py --psych --topic "Manipulasyon teknikleri"
```

### Gercek Suc Vakasi

```bash
# URL'den vaka cekip dedektif tarzi video uret
python run.py --vaka "https://tr.wikipedia.org/wiki/Vaka_sayfasi"
```

### Film Ozeti

```bash
# YouTube'dan trailer indir, spoiler'siz ozet anlat
python run.py --searchmovie --topic "Inception"
```

### Arama Kurtarma / Caught on Camera

```bash
# YouTube'dan video indir, 9:16 crop, dramatik yazi overlay, thumbnail uret
python run.py --rescue "https://youtube.com/watch?v=XXXX"
```

### Faz Kontrolleri

```bash
# Sadece belirli bir fazi calistir
python run.py --only-discovery
python run.py --only-script
python run.py --only-render

# Render yarim kaldiysa devam et
python run.py --only-render --resume-render

# Belirli bir uretim klasorunden devam et
python run.py --only-render --resume-render --from-output output/productions/2026-04-02_123456__konu
```

### Diger Secenekler

```bash
# Gameplay ustune AI gorselleri overlay olarak ekle
python run.py --withpics --topic "Konu"

# Simule et (API cagrisi yok)
python run.py --dry-run

# Video urettikten sonra yayinla (config/topic.yaml'da platform acik olmali)
python run.py --publish
```

---

## Klasor Yapisi

```
ChronicleX/
├── run.py                  # Giris noktasi
├── app/                    # CLI, ayarlar, config yukleyici
├── core/                   # Modeller, orchestrator, enum'lar
├── modules/
│   ├── scripting/          # Script uretimi (topic, vaka, film, psych)
│   ├── voice/              # ElevenLabs TTS
│   ├── visuals/            # DALL-E, Lexica, trailer indirme
│   ├── render/             # FFmpeg, altyazi, media pipeline
│   ├── rescue/             # Arama kurtarma modu (indirme, edit, overlay)
│   ├── publishers/         # YouTube, TikTok, Instagram yukleme
│   ├── topic_discovery/    # Konu kesfi (OpenAI + DB)
│   └── ...
├── config/                 # topic.yaml, styles.yaml
├── storage/                # PostgreSQL modelleri ve repository'ler
├── assets/
│   ├── backgrounds/        # Gameplay arka plan videolari (.mp4)
│   └── ambient/            # Ambient ses dosyalari (.mp3)
├── output/                 # Uretilen videolar (gitignore)
├── tests/                  # Pytest testleri
└── scripts/                # Migration ve yardimci scriptler
```

---

## PostgreSQL (Opsiyonel)

Sadece `--only-discovery` (konu kesfi) kullanacaksan gerekli.

```bash
# Docker ile
docker compose up -d

# .env'ye ekle:
# DATABASE_URL=postgresql+psycopg2://chroniclex:chroniclex@127.0.0.1:5433/chroniclex

# Tablolari olustur
python run.py --init-db

# Konu kesfi calistir
python run.py --only-discovery
```

---

## Gameplay Arka Plan

`assets/backgrounds/` klasorune `.mp4` dosyalari koy. Pipeline rastgele birini secer ve arka plan olarak kullanir. Klasor bossa DALL-E gorsel moduna gecer.

## Ambient Ses

`assets/ambient/` klasorune `.mp3` dosyalari koy. `--vaka` ve `--searchmovie` modlarinda otomatik olarak voice'un altina ambient ses karsitirilir.

---

## Test

```bash
# Birim testleri
pytest

# PostgreSQL entegrasyon testleri dahil (Docker acik olmali)
CHRONICLE_INTEGRATION=1 pytest tests/ -v
```
