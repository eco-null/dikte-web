# Dikte Web

Tek kullanıcılı, self-hosted konuşmadan yazıya web uygulaması. Dikte'nin Qt'siz
çekirdeği (FastAPI + HTMX, stdlib-only) üzerine kuruludur: dikte, dosya
transkripsiyonu, toplantı tutanakları, bir ajan, geçmiş ve ayarlar.

Bu repo, [yusufipk/dikte](https://github.com/yusufipk/dikte) projesinin bir
fork'udur. Orijinal çekirdek mantık ve transkripsiyon altyapısı
[yusufipk/dikte](https://github.com/yusufipk/dikte)'den türetilmiştir; burada
Qt masaüstü arayüzü çıkarılmış ve yerine FastAPI + HTMX web arayüzü konmuştur.

## Kurulum (Docker)

1. Bir `.env` dosyası oluştur:
   ```
   DIKTE_WEB_PASSWORD=sifreniz
   OPENAI_API_KEY=sk-...        # opsiyonel
   GROQ_API_KEY=...             # opsiyonel
   OPENROUTER_API_KEY=...       # opsiyonel
   ```
2. Başlat:
   ```
   docker compose up -d
   ```
3. http://localhost:8000 adresine git, şifreyle gir.

Veri, `dikte_data` volume'unda `/data` altında tutulur (config.json,
history.jsonl, meetings/, web_password, assistant.json). Restart sonrası korunur.

## Kullanım

- **Dikte**: mikrofon kaydı → transkript (otomatik temizlik opsiyonel).
- **Dosya**: ses/video dosyası yükle → txt/srt indir.
- **Toplantı**: mono veya stereo kayıt → tutanak (katılımcı adları opsiyonel).
- **Ajan**: soru sor, ayarlanan provider'dan cevap al.
- **Geçmiş**: kayıtlar listelenir ve temizlenir.
- **Ayarlar**: provider, API anahtarı, model, toplantı/ajan seçenekleri.

## OmniRoute

OmniRoute, OpenAI-uyumlu bir yerel uçtur. Varsayılan adres
`http://host.docker.internal:20128/v1` (compose `host-gateway` ile Docker'dan
erişilir). Ayar ucu modelini ve base_url'ini Ayarlar'dan değiştirebilirsin;
`OMNIROUTE_BASE_URL` env'i de varsayılanı ezebilir.

## Geliştirme

```
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

Notlar:

- ffmpeg, `_to_wav`/`_to_mp3`/`_ffmpeg` çağrılarını mock eden testler dışında
  gerekir (Docker imajı kurar; lokal makinede PATH'e ekle).
- Testler Windows'ta POSIX chmod testlerini skip eder.

## Güvenlik

Tek şifre, tek kullanıcı, HMAC imzalı cookie. WAN'a (internete) açmayın;
yalnızca kendi ağında veya ters proxy arkasında kullanın.
