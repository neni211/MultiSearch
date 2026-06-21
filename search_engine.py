"""
DuckDuckGo HTML endpoint üzerinden arama.

Not: duckduckgo-search paketi bu ortamda Bing'e düştüğü için
güvenilir değil. Bu yüzden paketin altında yatan
https://html.duckduckgo.com/html/ endpoint'ine doğrudan
requests + BeautifulSoup ile gidiyoruz. Sonuç olarak:
- API anahtarı yok
- Ücretsiz
- Üyelik yok
Aynı kullanıcı niyetini (ücretsiz, kural tabanlı) koruyor.
"""

import warnings

# urllib3'ün "InsecureRequestWarning" uyarılarını bastır
# (verify=False kullandığımız için bu beklenen bir durum)
import urllib3

import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

DDG_HTML_URL = "https://html.duckduckgo.com/html/"

# Tarayıcı gibi görünmek için standart User-Agent; aksi halde DDG bot koruması tetiklenir
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}


def search(query: str, max_results: int = 5, verify_ssl: bool = False) -> list[dict]:
    """
    DuckDuckGo HTML endpoint'inden arama sonuçlarını döndürür.

    Parametreler:
        query: arama sorgusu (string)
        max_results: istenen maksimum sonuç sayısı
        verify_ssl: SSL doğrulaması (ortam kısıtı nedeniyle False gerekebilir)

    Dönüş:
        [{"title": "...", "href": "https://..."}, ...] listesi
        Hata durumunda boş liste döner; çağıran taraf bunu kullanıcıya bildirmeli.
    """
    if not query or not query.strip():
        return []

    # Reklam linkleri duckduckgo.com/y.js?ad_domain=... kalıbında geliyor;
    # bunları filtrelemek için sonradan kontrol edeceğiz
    try:
        response = requests.post(
            DDG_HTML_URL,
            data={"q": query, "kl": "us-en"},
            headers=HEADERS,
            timeout=20,
            verify=verify_ssl,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("  [Uyarı] Arama servisine bağlanırken zaman aşımı.")
        return []
    except requests.exceptions.SSLError:
        print("  [Uyarı] SSL doğrulama hatası (sertifika zinciri).")
        return []
    except requests.exceptions.RequestException as e:
        # Diğer tüm requests hataları (ConnectionError, HTTPError, ...)
        print(f"  [Uyarı] Arama hatası: {type(e).__name__}")
        return []

    # Yanıtı parse et
    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    # DDG HTML lite'taki sonuç linkleri için standart seçici
    for a_tag in soup.select("a.result__a"):
        href = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        # Reklam linklerini atla (DDG bunları redirect URL olarak gösterir)
        if "duckduckgo.com/y.js" in href or "ad_domain=" in href:
            continue

        # Boş/geçersiz linkleri atla
        if not href or not href.startswith("http"):
            continue

        results.append({"title": title, "href": href})
        if len(results) >= max_results:
            break

    return results