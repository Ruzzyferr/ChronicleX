# --searchmovie + Prompt Kalite Iyilestirmesi

## Problem

1. Mevcut topic_narration prompt'u bazen felsefi/metaforik cumleler uretiyor ("korkunun seyi icimizde saklidir" tarzi). Izleyici "e bu neydi" diyor. Somut, dogrulanabilir, gercek bilgiye dayali anlatim gerekiyor.
2. Film icerigi icin yeni bir mod lazim: YouTube'dan trailer indir, kesitlerini birlestir, spoiler'siz ama merak uyandiran bir ozet anlat.

## Kapsam

### A. Mevcut Prompt Duzeltmesi (normal topic modu)

**Dosya:** `modules/scripting/topic_narration.py` — `TOPIC_NARRATION_SYSTEM` prompt'u guncellenir.

Yeni kurallar (prompt'a eklenecek):
- Felsefi/metaforik cumleler YASAK. "Korku icimizde saklidir", "tarihin karanlik yuzune bakmak" gibi soyut ifadeler kullanma.
- Her cumle somut bir bilgi, olay, kisi, tarih veya yer icermeli.
- Kaynak gosterilebilir gerceklerle ilerle. "Rivayete gore" degil, "1893'te Arthur Conan Doyle'un yazdigi..." gibi.
- Izleyici videonu bitirdiginde en az 3 somut bilgi ogrenmis olmali.
- "Biliyor muydunuz" tarzi ucuz hook'lar yerine, dogrudan olaya gir.
- Kapanista felsefe yapma. Son cumle de somut olsun — bir sonuc, bir rakam, bir gercek.

### B. --searchmovie Modu

#### B1. CLI + Model Degisiklikleri

- `app/cli.py`: `--searchmovie` flag (store_true)
- `core/models.py`: `RunContext.search_movie: bool = False`
- `app/cli.py` run_with_args: `search_movie=args.searchmovie`

#### B2. YouTube Trailer Indirme

**Yeni dosya:** `modules/visuals/trailer_dl.py`

```python
def search_and_download_trailer(
    topic: str,
    output_dir: Path,
    max_duration: int = 300,
) -> Path | None:
```

- yt-dlp kutuphanesi kullanilir (requirements.txt'e eklenir)
- Arama sorgusu: `"{topic} official trailer"` 
- Filtreler: sure < 5 dakika, video (ses yok indirilir — `-f bestvideo[height<=720]`)
- Cikti: `output_dir/trailer.mp4`
- Basarisizlik: None don, pipeline durdurulur
- yt-dlp'nin Python API'si kullanilir (`yt_dlp.YoutubeDL`)

#### B3. Film Ozet Script'i

**Yeni dosya:** `modules/scripting/movie_narration.py`

Ozel system prompt kurallari:
- Filmin ozetini anlat: ana karakter, durum, catisma, gerilim noktasi
- Spoiler VERME — klimaks ve final ANLATILMAZ
- Metafor/felsefe YASAK. Somut olay akisi.
- Izleyiciyi merakta birak: filmdeki somut bir olayi anlat ve oradan soru sor. Ornek: "Yillardir yalniz yasayan bu kadin, onu takip eden kisiyi fark etti. Ama takip eden kimdi? Ve ne istiyordu?" — gercek plot noktasindan turetilmis, somut, merak uyandiran sorular.
- "Tam bu noktada beklenmedik bir sey olur" gibi generic cliffhanger YASAK. Soru her zaman filmdeki gercek bir sahneye/olaya dayali olmali.
- "Bu filmde neler olacagini ogrenmek icin izlemelisiniz" tarzinda ucuz CTA yok
- Anlatim tonu: arkadas ortaminda film anlatan biri gibi, dogal ve akici
- Turk Turkce, TikTok formati, kisa vurucu cumleler

Fonksiyon:
```python
def write_movie_script_and_scenes(
    topic: TopicConfig,
    output_base: Path,
    api_key: str,
    model: str,
) -> list[Scene]:
```

Mevcut `write_topic_script_and_scenes` ile ayni cikti formati (script.txt + topic_scenes.json) uretir. Boylece render pipeline'i degismez.

#### B4. Trailer Kesitleme

**Guncellenen dosya:** `modules/render/ffmpeg_runner.py`

Yeni fonksiyon:
```python
def cut_and_concat_trailer_clips(
    trailer_path: Path,
    output_mp4: Path,
    target_duration: float,
    clip_length: float = 5.0,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> None:
```

Mantik:
1. `ffprobe` ile trailer suresini ol (T saniye)
2. Kesit sayisi: `N = ceil(target_duration / clip_length)` (ornegin 60/5 = 12 kesit)
3. Trailer'dan esit aralikla N nokta sec: `[0, T/N, 2*T/N, ...]`
4. Her noktadan `clip_length` saniyelik segment kes, 1080x1920'ye scale et
5. Tum segmentleri birlestir → `output_mp4`
6. Ses dahil edilmez (`-an` flagi)

#### B5. Pipeline Entegrasyonu

**Guncellenen dosya:** `core/orchestrator.py`

`_simulate_scripting` icinde: `search_movie=True` ise `movie_narration.write_movie_script_and_scenes` cagir.

**Guncellenen dosya:** `modules/render/media_pipeline.py`

`run_media_pipeline` icinde `search_movie=True` ise:
1. `search_and_download_trailer()` ile trailer indir
2. Ses uret (TTS)
3. `cut_and_concat_trailer_clips()` ile kesitleri birlestir (ses suresi kadar)
4. `mux_audio()` ile TTS ekle
5. `burn_subtitles()` ile altyazi yak → final.mp4

Bu akis, mevcut gameplay moduna cok benzer — sadece arka plan videosu `assets/backgrounds/` yerine indirilen trailer'dan geliyor.

### Bagimlilklar

- `yt-dlp>=2024.1.0` — requirements.txt'e eklenir
- Mevcut: openai, httpx, ffmpeg

### Dogrulama

1. `python run.py --topic "Inception" --searchmovie` — trailer indirilir, kesitler birlestirilir, film ozeti anlatilir
2. `python run.py --topic "Sherlock Holmes'i en cok zorlayan vaka"` — somut, felsefesiz, gercek bilgiye dayali anlatim
3. `pytest tests/` — mevcut testler gecmeli
4. Uretilen script.txt dosyasinda felsefi/metaforik cumle olmamali
5. Film videosunda trailer kesitleri gorulmeli, trailer sesi duyulmamali
