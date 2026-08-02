# Dikte Web

> **[Read in English](README.md)** · [İngilizce okuyun](README.md)

**Dikte Web**, tek kullanıcılı, kendi sunucunda barındırabileceğin (self-hosted)
bir konuşmadan yazıya web uygulamasıdır. Linux için yazılmış
[yusufipk/dikte](https://github.com/yusufipk/dikte) sesli dikte uygulamasının
web yeniden yazımıdır: Qt masaüstü kabuğu çıkarılır, aynı transkripsiyon motoru
tarayıcıdan kullanılan **FastAPI + HTMX** arayüzüyle sunulur.

Bu depo, [yusufipk/dikte](https://github.com/yusufipk/dikte) projesinin bir
**fork'udur**. Çekirdek transkripsiyon motoru, VAD, temizleme promptları,
toplantı hattı ve ajan mantığı orijinal projeden türetilmiştir; Qt masaüstü
arayüzü burada bir web arayüzüyle değiştirilmiştir. Orijinal masaüstü kodu
`upstream-dikte` dalında korunur.

---

## Özellikler

- **Dikte** — tarayıcıdan sesini kaydet, transkript al; isteğe bağlı AI
  temizliği dolgu sözcüklerini ("yani", "hani", "şey"), kekemeleri ve düşünme
  seslerini siler, noktalama ekler ve yanlış duyulan sözcükleri düzeltir.
- **Dosya transkripsiyonu** — bir ses veya video dosyası yükle (mp3, m4a, mp4,
  wav, …), sonucu düz metin veya **SRT altyazı** olarak indir.
- **Toplantı tutanağı** — mono veya stereo bir kayıt yükle; uygulama kaydı
  yazıya çevirir, konuşanları ayırır (sen / karşı taraf) ve özetli bir
  **markdown tutanak** üretir.
- **Ajan** — yapılandırılmış bir asistana soru sor, konuşma geçmişiyle cevap al.
- **Geçmiş** — her dikte aranabilir bir listeye kaydedilir ve temizlenebilir.
- **Ayarlar** — tüm transkripsiyon, temizleme, toplantı ve ajan seçenekleri web
  arayüzünde. API anahtarları maskelenir, yalnızca değiştirilir, asla
  gösterilmez.

## Arayüz

- **Modern koyu arayüz** — turkuaz/turuncu vurgu paleti ve Inter tipografisi.
- **Klavye navigasyonu** — her kontrolün görünür bir odak halkası vardır;
  arayüz `prefers-reduced-motion` özelliğini de destekler, isteyenler için
  animasyonları yatıştırır.
- **Bölümlü Ayarlar** — transkripsiyon, temizleme, yerel modeller, toplantılar
  ve ajan seçenekleri bölümlere ayrılmıştır; ayrıca whisper.cpp / llama.cpp
  ikili dosyalarını ve model dosyalarını doğrudan arayüzden kuran bir
  **Modeller** yöneticisi vardır.

## Dil desteği

Arayüz **İngilizce ve Türkçe** gelir. Ayarlar'dan `ui_language` değerini
`auto`, `en` veya `tr` yap; `auto` yerel ayarına göre tahmin eder. Temizleme ve
toplantı promptları da dile özeldir.

## Transkripsiyon sağlayıcıları

Ayarlar'dan şunlardan biri transkripsiyon sağlayıcısı olarak seçilebilir:

| Sağlayıcı | Taban URL | Varsayılan model |
|-----------|-----------|------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-transcribe` |
| Groq | `https://api.groq.com/openai/v1` | `whisper-large-v3-turbo` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-transcribe` |
| Local (whisper.cpp) | none (bu makinede çalışır) | whisper `.bin` modeli (Ayarlar → Modeller'den kurulur) |

Ajan **OpenRouter** (bulut) ve **OmniRoute**'u (yerel, OpenAI-uyumlu bir uç)
destekler; ikincisi kendi ağındaki makineler, örn. yerel bir LLM sunucusu için
tasarlanmıştır.

---

## Hızlı başlangıç (Docker)

1. Proje dizininde bir `.env` dosyası oluştur:

   ```dotenv
   DIKTE_WEB_PASSWORD=şifreniz
   OPENAI_API_KEY=sk-...            # opsiyonel
   GROQ_API_KEY=...                 # opsiyonel
   OPENROUTER_API_KEY=...           # opsiyonel
   OMNIROUTE_BASE_URL=http://host.docker.internal:20128/v1   # opsiyonel
   ```

   `DIKTE_WEB_PASSWORD` zorunludur (compose onsuz başlamayı reddeder). API
   anahtarları yalnızca gerçekte kullandığın sağlayıcılar için gerekir.

2. Uygulamayı başlat:

   ```bash
   docker compose up -d
   ```

3. http://localhost:8000 adresini aç ve şifreyle giriş yap.

İmaj **ffmpeg** kurar, yani her türlü ses/video dönüşümü kutudan çıktığı gibi
çalışır. Yüklemeler 1 GB ile sınırlıdır (`DIKTE_MAX_UPLOAD`).

### OmniRoute varsayılanı

`host.docker.internal`, Docker ana makinesine çözümlenir (compose bunu
`host-gateway` ile eşler). Ana makinede 20128 portunda yerel bir LLM sunucusu
çalıştırırsan ajan anında çalışır. Taban URL'yi ve modeli Ayarlar'dan
değiştirebilir veya `OMNIROUTE_BASE_URL` ortam değişkeniyle varsayılanı
ezebilirsin.

### Docker'sız çalıştırma

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Ana makinedeki gereksinimler:

- **Python 3.10+** (geliştirme ve test 3.14'te yapıldı).
- `PATH`'te **ffmpeg** (yüklemeleri WAV/MP3'e çevirmek için).
- `DIKTE_WEB_PASSWORD` değerini ayarla veya ilk başlangıçta üretilip basılan
  şifreyi oku (aşağıdaki *Kimlik doğrulama* bölümüne bak).

---

## Yapılandırma

### Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DIKTE_WEB_PASSWORD` | üretilir | Tek giriş şifresi. Boşsa rastgele üretilir, `web_password` dosyasına yazılır ve stderr'e basılır. |
| `XDG_CONFIG_HOME` | `~/.config` | `dikte/config.json` için taban. |
| `XDG_DATA_HOME` | `~/.local/share` | `dikte/` verisi için taban: geçmiş, toplantılar, kayıtlar, `web_password`, `assistant.json`. |
| `OPENAI_API_KEY` | — | Kolaylık env'i; asıl kaynak Ayarlar'dır. |
| `GROQ_API_KEY` | — | Aynı. |
| `OPENROUTER_API_KEY` | — | Aynı. |
| `OMNIROUTE_BASE_URL` | `http://host.docker.internal:20128/v1` | OmniRoute ajan ucunun varsayılanını ezme. |
| `DIKTE_MAX_UPLOAD` | `1073741824` (1 GB) | Maks. yükleme boyutu (üstüne 413). |

### Veri düzeni

Kalıcı her şey veri dizini altında durur (`$XDG_DATA_HOME/dikte`, Docker'da
`/data` olarak bağlanır):

```
dikte/
├── config.json          # ayarlar (web Ayarlar'ı bunu düzenler)
├── history.jsonl        # dikte geçmişi, her satır bir JSON kaydı
├── web_password         # üretilen şifre (yalnızca DIKTE_WEB_PASSWORD boşsa)
├── assistant.json       # ajan konuşma oturumu
├── recordings/          # yalnızca kayıt-tutma açıksa tutulur
└── meetings/
    ├── meetings.jsonl   # toplantı dizini
    ├── <base>.md        # üretilen tutanak
    └── <base>.wav       # toplantı sesi
```

### Web arayüzünde açık olan ayarlar

- **Genel** — `ui_language`
- **Transkripsiyon** — sağlayıcı, sağlayıcıya özel model ve API anahtarı,
  konuşma dili (`auto`/`tr`/`en`), prompt ipucu, **temizleme** anahtarı + model
  + akıl yürütme seviyesi, VAD seçenekleri (`skip_silent`, `silence_db`,
  `speech_margin_db`, `min_voiced_seconds`), halüsinasyon filtresi, geçmiş
  sınırı.
- **Toplantılar** — temizleme anahtarı, model, akıl yürütme, sen/karşı taraf
  adları, katılımcı listesi.
- **Ajan** — sağlayıcı (OpenRouter/OmniRoute), sağlayıcıya özel model, taban
  URL, oturum süresi (dakika), zaman aşımı.

### Yerel modeller

- **Ayarlar → Modeller** — `whisper.cpp` / `llama.cpp` ikili dosyalarını ve
  model dosyalarını (whisper `.bin` modelleri, GGUF quant dosyaları) doğrudan
  web arayüzünden kur.
- **Transkripsiyon** — bu makinede whisper.cpp ile yazıya çevirmek için
  `transcribe_provider` değerini `local` yap (API anahtarı gerekmez).
- **Temizleme** — transkriptleri llama.cpp ile yerel olarak temizlemek için
  `cleanup_provider` değerini `local-llm` yap.
- **Veri yolları** — ikili dosyalar `/data/share/dikte/bin`, modeller
  `/data/share/dikte/models` (Docker'da `dikte_data` biriminde).

---

## Kimlik doğrulama

- Tek ortak şifre; kullanıcı hesabı yok.
- Giriş, imzalı, **httponly**, `SameSite=Lax` oturum çerezi verir; **7 gün**
  sonra dolar.
- Çerez, işlem başına rastgele bir pepper ile HMAC imzalıdır; yeniden
  başlatmalar arasında taklit edilemez.
- `DIKTE_WEB_PASSWORD` ayarlanmamışsa rastgele bir şifre üretilir,
  `web_password` dosyasına kaydedilir ve ilk başlangıçta günlüğe basılır.

> **Güvenlik notu:** bu, tek şifreyle korunan tek kullanıcılı bir uygulamadır.
> İnternete açmayın. Kendi ağında veya TLS'li bir ters proxy arkasında
> çalıştırın.

---

## HTTP API

Uygulama, HTMX'in sürdüğü ince bir JSON API'sidir. Aşağıdaki uçların tümü giriş
kapısının arkasındadır (oturum yoksa `/api/*` → `401`).

| Metot | Yol | Amaç |
|-------|-----|------|
| `POST` | `/login` | Giriş (form alanı `password`). |
| `GET` | `/logout` | Çıkış. |
| `POST` | `/api/dictate` | Dikte işi başlat (multipart `audio`). |
| `POST` | `/api/files/transcribe` | Dosya transkripsiyon işi başlat (`file`, `timestamps`, `cleanup`). |
| `POST` | `/api/meetings` | Toplantı işi başlat (`file`, `participants`). |
| `GET` | `/api/meetings` | Toplantıları listele (yeniden eskiye). |
| `GET` | `/api/meetings/{base}` | Toplantı detayı + üretilen belge. |
| `POST` | `/api/meetings/{base}/retry` | Toplantı hattını yeniden çalıştır. |
| `DELETE` | `/api/meetings/{base}` | Toplantıyı sil. |
| `POST` | `/api/agent` | Ajana sor (`{"question": "…"}`). |
| `GET` | `/api/jobs/{id}` | İşin durumunu/sonucunu yokla. |
| `GET` | `/api/jobs/{id}/download?format=txt\|srt` | Transkripti indir. |
| `GET` | `/api/history` | Geçmişi listele. |
| `POST` | `/api/history/clear` | Geçmişi temizle. |
| `DELETE` | `/api/history` | Seçili satırları sil (`{"rows": […]}`). |
| `GET` | `/api/settings` | Ayarları oku (anahtarlar maskeli). |
| `POST` | `/api/settings` | Ayarları kaydet. |
| `GET` | `/healthz` | Canlılık yoklaması (public; config dosyasının okunabildiğini denetler). |

### İşler

Transkripsiyon ve toplantı işleri arka plan thread'lerinde çalışır. `POST`
uçları anında `{"job_id": …}` döndürür; istemci `status` `done` veya `failed`
olana dek `GET /api/jobs/{id}` yoklar. Aynı anda yalnızca bir ağır iş çalışır —
ikinci bir iş göndermek **`409 Conflict`** döndürür. Tamamlanan işler otomatik
budanır (son 100 tanesi tutulur).

---

## Geliştirme

```bash
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

- Test takımı **412 test / 895 alt test**, hepsi yeşil (bazı POSIX'e özel chmod
  testleri Windows'ta atlanır).
- Testler ağı (sağlayıcıları) ve ffmpeg dönüşümlerini mock'lar; çekirdek
  fonksiyonlar gerçek WAV üretir, böylece hatlar uçtan uca çalışır.

```
pytest                            # hepsini çalıştır
pytest tests/test_routes.py -v    # web E2E takımı
```

## Proje düzeni

```
app/
├── main.py                # FastAPI uygulaması, giriş kapısı, /healthz
├── auth.py                # tek şifreli giriş + imzalı çerez
├── jobs.py                # arka plan iş çalıştırıcı (aynı anda 1, budama)
├── settings.py            # web'e açık ayar dilimi + maskeleme
├── rms.py                 # ses seviyesi serisi (dalga formu için)
├── routes/
│   ├── pages.py           # HTML sayfaları (Jinja2)
│   └── api.py             # JSON uçları
├── static/                # CSS, app.js, recorder.js, htmx
├── templates/             # dikte, dosya, toplantı, ajan, geçmiş, ayarlar
└── vendor/dikte/          # (Qt'siz) orijinal motor:
    ├── api.py             # OpenAI/Groq/OpenRouter/yerel HTTP çağrıları
    ├── worker.py          # dikte hattı
    ├── filetranscribe.py  # dosya → txt/srt hattı
    ├── meeting.py         # toplantı → tutanak hattı
    ├── assistant.py       # ajan (OpenRouter / OmniRoute)
    ├── cleanup.py         # temizleme modeli çağrıları
    ├── config.py          # ayar saklama + varsayılanlar + promptlar
    ├── vad.py             # ses etkinliği tespiti
    ├── ggml.py            # yerel whisper.cpp / llama.cpp desteği
    ├── signals.py         # ilerleme yayını
    └── i18n.py            # en/tr string tablosu
tests/                     # tam takım (birim + web E2E)
```

## Teşekkür

- Orijinal proje: **[yusufipk/dikte](https://github.com/yusufipk/dikte)** —
  Linux için sesli dikte uygulaması. Tüm çekirdek motor kodu ondan türetilmiştir.
- Bu fork, Qt masaüstü arayüzünü çıkarır ve FastAPI + HTMX web arayüzü, tek
  şifreli kimlik doğrulama, arka plan işleri, yerel whisper.cpp/llama.cpp
  desteği ve Docker paketlemesi ekler.

## Katkıda Bulunanlar

- **[eco-null](https://github.com/eco-null)** — web yeniden yazımı: FastAPI +
  HTMX arayüzü, tek şifreli kimlik doğrulama, arka plan işleri, model yönetim
  arayüzü, modern koyu tasarım sistemi, Docker paketlemesi ve tam test takımı.

## Lisans

Orijinal lisans koşulları için yukarıdaki projeye bakın. Bu fork,
[yusufipk/dikte](https://github.com/yusufipk/dikte) ile aynı lisansı taşır.
