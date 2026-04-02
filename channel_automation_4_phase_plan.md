# Channel Automation System — 4 Fazlık Uygulama Planı

Bu doküman, Cursor içindeki Composer 2 veya Gemini 3.1 Pro (high) ile adım adım geliştirilebilecek, yeniden kullanılabilir bir **AI video automation app** için hazırlanmıştır.

## Ürün hedefi

Amaç, tek komutla çalışan bir sistem kurmaktır:

- kullanıcı `.env` dosyasını doldurur
- `config/topic.yaml` içinde kanal konusunu yazar
- komutu çalıştırır
- sistem uygun video konusunu bulur
- script yazar
- seslendirme ve video üretir
- YouTube / TikTok / Instagram'a yükler

## Kullanım hedefi

```bash
python run.py --topic "Bilinmeyen şaşırtıcı tarihi gerçekler"
```

veya sadece config dosyasından okuyacak şekilde:

```bash
python run.py
```

---

# Genel kurallar

## Teknik yaklaşım

- Ana dil: Python 3.11+
- Uygulama tipi: CLI-first reusable app
- DB: SQLite ile başla, sonra Postgres'e geçilebilir
- Render: FFmpeg tabanlı pipeline
- LLM / TTS / image/video generation: API tabanlı
- Publisher'lar: modüler yapı
- Yapılandırma: `.env` + `config/*.yaml`

## Mimari prensipleri

1. Her modül ayrı olmalı.
2. Tüm provider'lar değiştirilebilir olmalı.
3. Uygulama tek kullanıcıya özel değil, tekrar kullanılabilir olmalı.
4. Arkadaşına verdiğinde sadece `.env` ve config değişerek çalışmalı.
5. İlk sürümde UI yapılmayacak; CLI yeterli.
6. Hata logları ve adım bazlı kayıt şart.
7. Publish katmanı üretim katmanından ayrı olmalı.
8. Kod production'a yakın ama sade tutulmalı.

## Kod standardı

- type hints kullan
- pydantic settings kullan
- modüler servis yapısı kur
- magic string ve hardcoded path kullanma
- tüm dış servis erişimleri adapter/service class içinde olsun
- retry mantığı ekle
- her adım loglansın
- README ve `.env.example` eksiksiz olsun

---

# Önerilen proje yapısı

```text
channel-automation/
  app/
    cli.py
    main.py
    settings.py

  core/
    orchestrator.py
    models.py
    enums.py
    exceptions.py

  modules/
    topic_discovery/
      service.py
      prompts.py
      schemas.py
    novelty/
      service.py
      rules.py
    verification/
      service.py
      prompts.py
    scripting/
      service.py
      prompts.py
    voice/
      service.py
    visuals/
      service.py
    render/
      service.py
    publishers/
      youtube.py
      tiktok.py
      instagram.py
    analytics/
      service.py

  storage/
    db.py
    models.py
    repositories/
    migrations/

  config/
    topic.yaml
    styles.yaml

  data/
    app.db

  output/
    logs/
    scripts/
    audio/
    images/
    videos/
    subtitles/

  tests/

  .env.example
  requirements.txt
  README.md
  run.py
```

---

# Faz 1 — Temel iskelet + yapılandırma + CLI

## Faz hedefi

İlk fazın amacı çalışan bir temel ürün iskeleti oluşturmaktır. Bu faz sonunda kullanıcı:

- projeyi klonlayabilmeli
- bağımlılıkları kurabilmeli
- `.env` dosyasını oluşturabilmeli
- `config/topic.yaml` yazabilmeli
- `python run.py` ile uygulamayı başlatabilmeli
- dry-run alabilmeli

## Bu fazda yapılacaklar

### 1. Proje iskeleti
Aşağıdaki klasörleri ve temel dosyaları oluştur:

- `app/`
- `core/`
- `modules/`
- `storage/`
- `config/`
- `output/`
- `tests/`

### 2. Settings sistemi
`pydantic-settings` veya benzeri bir yapı ile şu ayarları yönet:

- OPENAI_API_KEY
- TTS_API_KEY
- IMAGE_API_KEY
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN
- TIKTOK_CLIENT_KEY
- TIKTOK_CLIENT_SECRET
- INSTAGRAM_ACCESS_TOKEN
- INSTAGRAM_ACCOUNT_ID
- OUTPUT_DIR
- DATABASE_URL
- DEFAULT_LANGUAGE
- DEFAULT_TIMEZONE
- DRY_RUN

### 3. Config dosyaları
`config/topic.yaml` ve `config/styles.yaml` oluştur.

#### Örnek `topic.yaml`

```yaml
topic_name: "Bilinmeyen şaşırtıcı tarihi gerçekler"
language: "tr"
tone: "karanlık, gizemli, sinematik, çarpıcı"
video_duration_seconds: 45

content_rules:
  must_be_real: true
  avoid_repetition: true
  minimum_shock_score: 8
  minimum_verification_score: 7
  min_sources: 2

publishing:
  youtube_enabled: true
  tiktok_enabled: true
  instagram_enabled: true
```

### 4. CLI
`python run.py` ve argümanlı kullanım desteklenmeli:

- `--topic`
- `--config`
- `--dry-run`
- `--publish`
- `--only-discovery`
- `--only-script`
- `--only-render`
- `--only-publish`

### 5. Logging
Aşağıdakileri logla:

- uygulama başlangıcı
- seçilen config
- aktif topic
- her fazın başlangıç/bitişi
- hata mesajları
- üretilen dosya yolları

### 6. README
README içinde şunlar olmalı:

- kurulum
- `.env` hazırlama
- config örneği
- komut örnekleri
- publish akışının nasıl çalıştığı
- dry-run açıklaması
- sık karşılaşılan hatalar

## Faz 1 çıktıları

Bu faz sonunda aşağıdakiler çalışıyor olmalı:

- `python run.py --dry-run`
- config yükleme
- env yükleme
- klasör oluşturma
- log dosyası oluşturma
- placeholder orchestrator çalışması

## Kabul kriterleri

- proje sıfırdan kurulabiliyor olmalı
- `.env.example` eksiksiz olmalı
- CLI en az 5 argüman desteklemeli
- dry-run modunda uygulama hata vermeden tüm adımları simüle etmeli
- kod modüler olmalı, tek dosyada toplanmamalı

---

# Faz 2 — Topic discovery + novelty + verification + persistence

## Faz hedefi

Bu fazın amacı, kullanıcı konusuna uygun günlük içerik adayları bulmak, tekrarları engellemek, doğrulama yapmak ve veritabanına kaydetmektir.

## Bu fazda yapılacaklar

### 1. Veritabanı tasarımı
SQLite ile şu tabloları oluştur:

#### `topics`
- id
- channel_topic
- title
- summary
- event_year
- country
- region
- category
- subcategory
- people_involved
- source_count
- source_1
- source_2
- source_3
- shock_score
- fear_score
- clarity_score
- visual_score
- novelty_score
- verification_score
- is_verified
- is_used
- created_at
- updated_at

#### `published_videos`
- id
- topic_id
- channel_topic
- script_path
- audio_path
- video_path
- youtube_status
- tiktok_status
- instagram_status
- published_at

#### `editorial_memory`
- id
- channel_topic
- recent_titles_json
- recent_countries_json
- recent_centuries_json
- recent_categories_json
- recent_people_json
- recent_hook_patterns_json
- updated_at

#### `job_runs`
- id
- job_name
- status
- details_json
- error_message
- created_at

### 2. Topic discovery service
Servis şu akışı yapmalı:

- config'teki ana konuyu al
- bu konuya göre 20–50 aday video konusu üret
- dış kaynaklardan bilgi çekebilecek şekilde adapter tabanı oluştur
- adayları normalize et
- kısa özet çıkar
- kategori ata

Not: provider mantığı değiştirilebilir olsun.

### 3. Novelty engine
Geçmiş konularla çakışmayı engelleyen mantık kur:

- aynı olay tekrar etmesin
- aynı kişi sık tekrar etmesin
- aynı ülke üst üste gelmesin
- aynı kategori sık tekrar etmesin
- başlık kalıbı tekrar etmesin

İlk sürümde basit string / metadata tabanlı kıyaslama olabilir.
Daha sonra embedding similarity eklenebilecek şekilde yaz.

### 4. Verification engine
Her konu için:

- olay özeti çıkar
- olayın gerçek, tarihsel ve anlatılabilir olup olmadığını değerlendir
- en az 2 kaynak kuralı uygula
- verification_score üret
- eşik altıysa reddet

### 5. Topic scoring
Her aday için puanlar üret:

- shock_score
- fear_score
- clarity_score
- visual_score
- novelty_score
- verification_score

Sonra en iyi adayı seç.

### 6. Persistence
Tüm adaylar DB'ye yazılmalı.
Seçilen aday ayrıca `selected` veya `ready_for_script` olarak işaretlenmeli.

## Faz 2 çıktıları

Bu faz sonunda uygulama şunları yapmalı:

- ana topic'e göre aday bulmalı
- adayları puanlamalı
- tekrarları elemeli
- doğrulama yapmalı
- en iyi adayı seçmeli
- DB'ye yazmalı

## Kabul kriterleri

- `python run.py --only-discovery` çalışmalı
- en az 10 aday üretmeli
- en az 1 seçilmiş konu DB'ye kaydolmalı
- duplicate kontrolü olmalı
- verification adımı ayrı service class içinde olmalı
- aynı topic ikinci çalıştırmada aynı sonucu kolayca seçmemeli

---

# Faz 3 — Script + voice + visuals + render pipeline

## Faz hedefi

Bu fazın amacı seçilmiş ve doğrulanmış konudan tam video paketi üretmektir.

## Bu fazda yapılacaklar

### 1. Script engine
Seçilen topic için aşağıdakileri üret:

- 10 başlık alternatifi
- 3 hook alternatifi
- 1 final kısa script
- 1 kapanış cümlesi
- platform caption taslakları

Kurallar:

- 35–60 saniyelik dikey video uyumlu olmalı
- kısa cümleler kullanılmalı
- ilk 2 saniye hook etkili olmalı
- doğrulanmamış iddia eklenmemeli
- ton config'ten alınmalı

### 2. Scene planner
Script'i sahnelere böl:

Her sahne için JSON üret:

- scene_number
- duration_seconds
- narration_line
- visual_prompt
- text_overlay
- camera_motion
- transition_type
- sound_mood

### 3. Voice service
TTS entegrasyonu yap:

- final script'i seslendir
- mp3 veya wav üret
- output klasörüne kaydet
- hata olursa logla
- farklı voice provider'lar için adapter mantığı kur

### 4. Visual service
Her sahne için görsel üretim girdisi hazırla:

- prompt oluştur
- isteğe göre image API kullan
- ya da placeholder asset sistemi kur
- çıktı dosyalarını düzenli klasöre kaydet

### 5. Subtitle generation
Script veya TTS sonuçlarından altyazı dosyası üret:

- `.srt` ya da `.ass`
- satırlar çok uzun olmasın
- kısa bloklar halinde olsun

### 6. Render engine
FFmpeg tabanlı ilk render pipeline kur:

- dikey 1080x1920 video üret
- sahne görsellerini sırala
- hafif zoom/pan ekle
- seslendirmeyi ekle
- altyazıyı göm
- final mp4 üret

### 7. Asset manifest
Her üretim sonunda JSON manifest oluştur:

- topic id
- selected title
- script path
- audio path
- subtitle path
- image paths
- final video path

## Faz 3 çıktıları

Bu faz sonunda uygulama şunları yapmalı:

- doğrulanmış topic'ten script üretebilmeli
- ses dosyası üretebilmeli
- sahne planı hazırlayabilmeli
- en az placeholder görsellerle video oluşturabilmeli
- final mp4 dosyasını kaydedebilmeli

## Kabul kriterleri

- `python run.py --only-render` çalışmalı
- final script dosyası oluşmalı
- final audio dosyası oluşmalı
- subtitle dosyası oluşmalı
- final `.mp4` üretilebilmeli
- tüm dosya yolları log ve DB'de kayıtlı olmalı

---

# Faz 4 — Publishing + analytics + reusable handoff

## Faz hedefi

Bu fazın amacı üretilen videonun platformlara gönderilmesi, sonuçların kaydedilmesi ve projenin başka bir kullanıcıya verilebilir hale getirilmesidir.

## Bu fazda yapılacaklar

### 1. Publisher interface
Ortak bir publisher sözleşmesi oluştur:

- `publish(video_asset, metadata)`
- `validate_credentials()`
- `dry_run_preview()`

### 2. YouTube publisher
Aşağıdakileri destekle:

- video upload
- title
- description
- tags
- privacy status
- shorts uyumlu metadata
- sonuç id'sini kaydet

### 3. TikTok publisher
Aşağıdakileri destekle:

- video upload veya publish initialization
- caption
- publish sonucu kaydı
- hata durumunda log

### 4. Instagram publisher
Aşağıdakileri destekle:

- reels publish akışı
- caption
- publish sonucu kaydı
- hata yönetimi

### 5. Publish queue mantığı
Üretim ile paylaşımı ayır:

- `ready_to_publish`
- `published`
- `failed`
- `retry_pending`

### 6. Analytics snapshot
İlk sürümde basit kayıt yeterli:

- video hangi platforma gönderildi
- post id nedir
- tarih nedir
- publish başarılı mı

İleri sürüm için yer bırak:

- views
- likes
- comments
- watch time
- retention

### 7. Reusable handoff
Arkadaşına verilebilir hale getir:

- eksiksiz `.env.example`
- örnek `config/topic.yaml`
- örnek `styles.yaml`
- kurulum rehberi
- provider değişim rehberi
- sık hata rehberi

### 8. Safety and dry-run
Publish katmanında mutlaka şu olsun:

- `DRY_RUN=true` ise gerçek paylaşım yapma
- sadece payload ve hedef platform bilgisini logla

## Faz 4 çıktıları

Bu faz sonunda uygulama şunları yapmalı:

- final videoyu seçili platformlara gönderebilmeli
- başarılı/başarısız sonucu DB'ye yazabilmeli
- dry-run publish yapabilmeli
- farklı kullanıcı tarafından `.env` değiştirerek kullanılabilmeli

## Kabul kriterleri

- `python run.py --publish` çalışmalı
- platform publisher'ları ayrı modüllerde olmalı
- credential eksikse düzgün hata vermeli
- dry-run publish desteklenmeli
- README ile sıfırdan kurulum yapılabilmeli

---

# Composer 2 / Gemini için çalışma kuralları

Bu proje tek seferde üretilmeye çalışılmamalı.
Her faz ayrı uygulanmalı.

## Beklenen geliştirme sırası

1. Faz 1'i tamamla
2. Kodun çalıştığını doğrula
3. Sonra Faz 2'ye geç
4. Sonra Faz 3
5. En son Faz 4

## Her fazda zorunlu beklentiler

- çalışan kod üret
- dosya dosya ilerle
- eksik yerleri TODO olarak işaretle
- mock / dry-run imkanı bırak
- açıklamalı README güncelle
- gerekirse örnek `.env.example` ve config dosyalarını tamamla

## Yapılmaması gerekenler

- tüm sistemi tek dosyada yazma
- sahte implementasyonları çalışanmış gibi gösterme
- eksik credential gerektiren yerleri gizleme
- publish akışını render ile iç içe geçirme
- tekrarlı ve bakım zor bir yapı kurma

---

# Model seçimi önerisi

## Bu proje özelinde hangisi?

### Composer 2 seç
Şunlar için daha iyi aday:

- repo iskeleti kurma
- dosya dosya ilerleme
- agentic refactor
- Cursor içinde terminal + dosya + context ile çalışma
- modüler Python proje yazdırma

Cursor, Composer 2'yi ajan tabanlı yazılım geliştirme ve büyük kod tabanlarında çalışma için konumlandırıyor. Resmi dokümanlarda Composer 2 agentic coding modeli olarak anlatılıyor. citeturn124004search0turn124004search10

### Gemini 3.1 Pro (high) ne zaman daha iyi olabilir?

Şunlarda iyi yardımcı olabilir:

- üst seviye mimari düşünme
- prompt tasarımı
- alternatif sistem kurguları
- render veya içerik stratejisi için geniş düşünme

Google, Gemini 3.1 Pro'yu karmaşık görevler ve gelişmiş ajan yetenekleri için konumlandırıyor. citeturn124004search2turn124004search5

## Net tavsiye

Bu projede **ana yazıcı olarak Composer 2**, gerektiğinde **ikinci görüş / mimari danışman olarak Gemini 3.1 Pro (high)** daha mantıklı.

Sebep:

- sen Cursor içinde geliştireceksin
- proje dosya tabanlı ve ajan tarzı ilerleyecek
- repo iskeleti + iteratif kod üretimi gerekiyor
- Composer 2 Cursor içinde bu iş akışına daha doğal oturuyor citeturn124004search0turn124004search1turn124004search4turn124004search7

Pratik karar:

- **İlk denemeyi Composer 2 ile yap**
- takıldığı yerlerde **Gemini 3.1 Pro (high)** ile mimari / prompt / düzeltme desteği al

---

# Cursor'a verilecek kısa kullanım notu

Cursor içindeki modele şu kuralla ilerlemesini söyle:

1. Önce sadece Faz 1'i uygula.
2. Çalışan kod üret.
3. README ve `.env.example` güncelle.
4. Sonra Faz 2'ye geçmeden önce mevcut kodu test et.
5. Faz 2, Faz 3, Faz 4 aynı mantıkla sırayla tamamlansın.
6. Her faz sonunda hangi dosyaları oluşturduğunu ve nasıl test edileceğini yaz.

