# Dikte Web

> **[Read in English](README.md)** · [İngilizce okuyun](README.md)

<p align="center">
  <img src="app/static/logo.png" alt="Dikte Web" width="120">
</p>

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

   API anahtarları yalnızca gerçekte kullandığın sağlayıcılar için gerekir.
   Değerler isteğe bağlıdır; `DIKTE_WEB_PASSWORD` boş bırakılırsa uygulama
   kendisi bir şifre üretir ve veri volume'una kaydeder.

2. Uygulamayı başlat:

   ```bash
   docker compose up -d
   ```

3. http://localhost:8000 adresini aç ve şifreyle giriş yap.

İmaj **ffmpeg** kurar, yani her türlü ses/video dönüşümü kutudan çıktığı gibi
çalışır. Yüklemeler 1 GB ile sınırlıdır (`DIKTE_MAX_UPLOAD`).

> **Erişim:** `docker-compose.yml` servisi yalnızca **loopback**'e bağlar
> (`127.0.0.1:8000`). Önüne bir şey koymadıkça ana makinenin dışından
> erişilemez. İki seçenek aşağıda.

> **İmaj otomatik derlenir:** `master`'a her push, Docker imajını derleyip
> `ghcr.io/eco-null/dikte-web`'e `latest` (ve bir SHA etiketiyle) yayınlayan bir
> GitHub Actions işi başlatır. Compose'un yeni imajı alması için bir sonraki
> `docker compose up` öncesi `docker compose pull` çalıştırman yeterli.

### Cloudflare Tunnel ile yayınla (ters proxy gerekmez)

Cloudflare'da bir alan adın varsa `cloudflared` TLS'i Cloudflare kenarında
sonlandırır ve loopback portuna tünel açar — çalıştırman gereken bir ters
proxy yok:

1. Ana makineye `cloudflared` kur (bkz.
   [developers.cloudflare.com](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)).
2. Giriş yap ve tünel oluştur (bir kez):
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create dikte-web
   ```
3. `~/.cloudflared/config.yml` dosyasını yapılandır:
   ```yaml
   tunnel: dikte-web
   credentials-file: /home/KULLANICI/.cloudflared/KULLANICIID.json

   ingress:
     - hostname: dikte.ornek.com
       service: http://localhost:8000
     - service: http_status:404
   ```
4. DNS adını tünele bağla, sonra çalıştır (kalıcılık için systemd servisi
   olarak):
   ```bash
   cloudflared tunnel route dns dikte-web dikte.ornek.com
   cloudflared tunnel run dikte-web
   ```
5. `https://dikte.ornek.com` adresini aç ve şifreyle giriş yap.

Uygulama, login sınırlaması için Cloudflare'ın `CF-Connecting-IP` başlığını
zaten kullanır; böylece her gerçek ziyaretçi kendi deneme bütçesini alır.
`DIKTE_COOKIE_SECURE=1`'i açık bırak (varsayılan) — Cloudflare HTTPS sunar,
`Secure` çerez çalışır. Ek olarak 8000 portunu internete **açma**; tünel tek
giriş noktasıdır.

### OmniRoute varsayılanı

`host.docker.internal`, Docker ana makinesine çözümlenir (compose bunu
`host-gateway` ile eşler). Ana makinede 20128 portunda yerel bir LLM sunucusu
çalıştırırsan ajan anında çalışır.

**Ayarlar** (sayfa → *Assistant* bölümü), üç alan:

| Alan | Amaç |
|------|------|
| `assistant_provider` | **OmniRoute**'u seç |
| `assistant_omniroute_base_url` | uç adresi, ör. `http://host.docker.internal:20128/v1` |
| `assistant_omniroute_model` | model kimliği (ör. `gemma-3-4b-it`) |
| `assistant_omniroute_api_key` | **opsiyonel** — doluysa `Bearer` token olarak gönderilir; anahtarsız yerel uçlar için boş bırak |

Ayrıca `OMNIROUTE_BASE_URL` ortam değişkeniyle varsayılan uç adresini
ezebilirsin. Özel veya yerel bir adrese çözümlenen her taban URL, `host.docker.internal`,
`localhost` ve `127.0.0.1` dışındaysa reddedilir (SSRF koruması).

### Docker'sız çalıştırma

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Ana makinedeki gereksinimler:

- **Python 3.10+** (geliştirme ve test 3.14'te yapıldı).
- `PATH`'te **ffmpeg** (yüklemeleri WAV/MP3'e çevirmek için).
- `DIKTE_WEB_PASSWORD` değerini ayarla veya ilk başlangıçta üretilip
  `web_password` dosyasına kaydedilen şifreyi oku (aşağıdaki *Kimlik
  doğrulama* bölümüne bak).

---

## Yapılandırma

### Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DIKTE_WEB_PASSWORD` | üretilir | Tek giriş şifresi. Boşsa rastgele üretilir, `web_password` dosyasına yazılır (0600 izni, günlüğe yazılmaz). |
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
- `DIKTE_WEB_PASSWORD` ayarlanmamışsa rastgele bir şifre üretilir ve
  `web_password` dosyasına kaydedilir (0600 izni); asla günlüğe yazılmaz.

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

## Güvenlik

- **Tek şifre + hız sınırlama.** Uygulama tek bir ortak şifreyle korunur
  (`DIKTE_WEB_PASSWORD`). Giriş, istemci IP'si başına hız sınırlıdır
  (15 dakikada 5 başarısız deneme → `429`) ve şifre sabit zamanlı
  karşılaştırmayla denetlenir.
- **Oturum çerezi.** `dikte_session` çerezi `HttpOnly`, `SameSite=Lax` ve
  varsayılan olarak `Secure`'dur (`DIKTE_COOKIE_SECURE=1`). `Secure` bayrağını
  yalnızca güvenilir bir ağda düz HTTP üzerinden çalışıyorsan kapat
  (`DIKTE_COOKIE_SECURE=0`).
- **TLS gerekli — ama ters proxy şart değil.** Servis yalnızca loopback'e
  bağlanır (`127.0.0.1:8000`). Önüne TLS'li bir Caddy/nginx/Traefik proxy koy
  ya da — en basiti — yukarıda anlatıldığı gibi bir [Cloudflare Tunnel
  (`cloudflared`)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  ile yayınla; TLS'i Cloudflare kenarında sonlandırır ve loopback portuna
  tünel açar. 8000 portunu doğrudan internete açma.
- **CSRF koruması.** Değiştirici istekler aynı kökenden gelen
  `Origin`/`Referer` başlığına göre denetlenir; siteler arası istekler `403` ile
  reddedilir.
- **Markdown temizlenir.** Toplantı tutanakları HTML olarak gösterilirken nh3
  HTML temizleyicisinden geçirilir; böylece transkript içeriğinden gelen
  depolanmış XSS engellenir.
- **Birimi gizli tut.** `dikte_data` biriminde API anahtarları (`config.json`
  içinde) ve toplantı kayıtları düz metin olarak durur. Düzenli yedek al ve
  yalnızca senin okuyabildiğin dosya sistemlerinde sakla.

## Lisans

Orijinal lisans koşulları için yukarıdaki projeye bakın. Bu fork,
[yusufipk/dikte](https://github.com/yusufipk/dikte) ile aynı lisansı taşır.
