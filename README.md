# ChronicleX — Channel automation

CLI-first pipeline: **konu başlığı** → keşif → script → medya (FFmpeg). Varsayılan akışta **otomatik yayın yok**; çıktı `output/productions/<tarih>__<konu-slug>/` altında toplanır ( `OUTPUT_USE_PRODUCTION_SUBFOLDERS`, dry-run’da düz `output/`).

- **Faz 1:** yapılandırma, CLI, logging, orchestrator.
- **Faz 2:** PostgreSQL üzerinde topic discovery (OpenAI), novelty, verification, kalıcı kayıt; `--only-discovery` ile çalışır. `--dry-run` discovery’de API/DB yazımı yapmaz.
- **Faz 3:** OpenAI ile sahne planı, DALL·E görseller, ElevenLabs ses, SRT, FFmpeg ile dikey `video/final.mp4` + `manifest.json` (üretim klasörünün içinde). `--only-render` veya tam pipeline (dry-run kapalı). Gerekli: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` (veya `TTS_API_KEY`), sistemde **FFmpeg**.
- **Faz 4 (raf / isteğe bağlı):** YouTube, TikTok, Instagram yükleme kodu duruyor; `config/topic.yaml` `publishing` varsayılan kapalı. Açmak için bayrakları `true` yapıp `--publish` veya `--only-publish` kullanın. DB migration: `scripts/migration_faz4_publish_columns.sql`.

## Gereksinimler

- Python 3.11+
- Komutları **proje kökünden** çalıştırın (`run.py` göreli yolları buna göre çözer).

## Kurulum

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

`.env.example` dosyasını `.env` olarak kopyalayın. Aşağıdaki Docker + test akışı tamamlandıktan sonra **yapmanız gereken tek şey**, canlı API ve prod veritabanı için `.env` içindeki gerçek değerleri (özellikle `OPENAI_API_KEY`, `DATABASE_URL`, ileride platform anahtarları) doldurmaktır.

- **Dry-run:** API ve veritabanı gerekmez (`python run.py --dry-run`).
- **Canlı discovery:** `DATABASE_URL` + `OPENAI_API_KEY`.
- **Faz 3 render:** ayrıca `ELEVENLABS_API_KEY` (veya `TTS_API_KEY`) ve FFmpeg.

## Yapılandırma

- **Ortam:** `.env` — tüm anahtarlar [.env.example](.env.example) içinde listelenir.
- **Konu:** [config/topic.yaml](config/topic.yaml) — kanal konusu, dil, ton, içerik kuralları, hangi platformların açık olduğu.
- **Stil:** [config/styles.yaml](config/styles.yaml) — görsel/altyazı ipuçları (Faz 3’te kullanılacak).

## PostgreSQL — Docker ile (önerilen yerel ortam)

1. Proje kökünde:

```bash
docker compose up -d
```

2. Bağlantı hazır olana kadar:

```bash
python scripts/wait_for_postgres.py
```

3. `.env` içine (Docker varsayılanı):

`DATABASE_URL=postgresql+psycopg2://chroniclex:chroniclex@127.0.0.1:5433/chroniclex`

4. Şema:

```bash
python run.py --init-db
```

5. Keşif (OpenAI ücreti oluşur; `.env` içinde `OPENAI_API_KEY` gerekir):

```bash
python run.py --only-discovery
```

Kendi PostgreSQL sunucunuz varsa `docker-compose.yml` yerine doğrudan `DATABASE_URL` kullanabilirsiniz (`psql` ile veritabanı oluşturma adımları size kalmış).

## Faz 3 — Video üretimi (FFmpeg)

1. [FFmpeg](https://ffmpeg.org/download.html) kurulu olsun (`ffmpeg` / `ffprobe` PATH’te veya `.env` ile `FFMPEG_PATH` / `FFPROBE_PATH`).
2. `.env`: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` veya `TTS_API_KEY`, isteğe bağlı `ELEVENLABS_VOICE_ID`.
3. Anlatım metni: `output/scripts/script.txt` (satır başı `#` yorum sayılır) veya PostgreSQL’de bu kanal için `ready_for_script` olan topic (`title` + `summary`).
4. Sadece render:

```bash
python run.py --only-render
```

Tam pipeline’ı dry-run **olmadan** çalıştırmak discovery + script + render için API maliyeti doğurur.

Çıktılar: `output/images/scene_*.png`, `output/audio/voice.mp3`, `output/subtitles/subtitles.srt`, `output/video/final.mp4`, `output/video/manifest.json`.

## Test

Birim testleri (PostgreSQL gerekmez; entegrasyon testleri varsayılan olarak atlanır):

```bash
pytest
```

Docker Postgres açıkken **entegrasyon** testlerini de çalıştırmak için (PowerShell):

```powershell
$env:CHRONICLE_INTEGRATION="1"
pytest tests/ -v
```

Bash:

```bash
CHRONICLE_INTEGRATION=1 pytest tests/ -v
```

İsteğe bağlı: `CHRONICLE_TEST_DATABASE_URL` ile farklı bir Postgres URL’si verebilirsiniz; verilmezse `127.0.0.1:5433` Docker servisi kullanılır.

Windows’ta Docker + tüm testler tek seferde: [scripts/run_all_tests.ps1](scripts/run_all_tests.ps1) (proje kökünden `powershell -File scripts/run_all_tests.ps1`).

## Komut örnekleri

```bash
# Tüm pipeline’ı simüle et (önerilen ilk test)
python run.py --dry-run

# Konu adını komut satırından override et
python run.py --dry-run --topic "Özel bir başlık"

# Farklı topic yaml yolu
python run.py --dry-run --config config/topic.yaml

# Sadece tek faz (placeholder; Faz 2+ ile dolar)
python run.py --dry-run --only-discovery
python run.py --dry-run --only-script
python run.py --dry-run --only-render
python run.py --dry-run --only-publish

# Render yarım kaldıysa: son üretim klasöründe sahne/görsel/ses varsa atla (scenes.json + render_cache)
python run.py --only-render --resume-render
# Belirli klasör:
python run.py --only-render --resume-render --from-output output/productions/2026-04-02_123456__konu-slug

# Publish fazını tam pipeline’a dahil et (--ship, --publish ile eşanlamlı)
python run.py --dry-run --publish
python run.py --dry-run --ship

# [Raf] Sadece yayın: son üretilen video (productions içinde en yeni final.mp4 veya output/video/)
python run.py --dry-run --only-publish --topic "Videonun başlığı"
# Gerçek yükleme: publishing.* true + credential’lar; DRY_RUN=false
python run.py --only-publish --topic "Videonun başlığı"
```

## Yayın (isteğe bağlı)

Normal kullanımda pipeline yayını çalıştırmaz. `--publish` / `--ship` tam akışın sonuna yayın ekler; `--only-publish` en son videoyu arar. Ayrıntılar: `modules/publishers/`.

## Dry-run

- `--dry-run` veya `.env` içinde `DRY_RUN=true`: dış servislere çağrı yapılmaz, dosya yazımı minimum/placeholder seviyededir.
- Log çıktısı konsola ve çalışma klasöründeki `logs/app.log` dosyasına düşer (dry-run’da genelde `output/logs/`).

## Sık karşılaşılan hatalar

- **`Config file not found`:** `--config` yolunun proje köküne göre doğru olduğundan emin olun; varsayılan `config/topic.yaml`.
- **`ModuleNotFoundError`:** Komutu repo kökünden çalıştırın: `python run.py`.
- **`.env` okunmuyor:** Çalışma dizininin proje kökü olduğundan emin olun; pydantic-settings `.env` dosyasını kökten okur.

## Plan

Ayrıntılı faz planı: [channel_automation_4_phase_plan.md](channel_automation_4_phase_plan.md).
