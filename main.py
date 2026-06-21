"""
Çoklu Kaynak Arama — CLI giriş noktası.

Akış (her sorgu için):
  1. Kilit dosyası kontrolü (varsa çıkış)
  2. Kullanıcıdan soru al
  3. İçerik filtresi (yasaklıysa kilitle ve çık)
  4. DuckDuckGo ile arama
  5. Her sonuç için sayfa çek, temizle, TextRank skorlarıyla cümle seç
  6. Tüm kaynaklardan aday cümleleri global olarak sırala, dedupe et,
     en fazla 5 cümle seç
  7. Tek bir "Yanıt" panelinde akıcı metin olarak yazdır + süre bilgisi

REPL: Kullanıcı "çıkış", "exit" veya "q" yazana kadar döngü devam eder.

UI: rich (Panel, Spinner, Live) ile Claude Code tarzı sade görünüm —
teknik loglar spinner durum metninde gizlenir. Yanıt panelinde kaynak
ayrımı (Kaynak N, URL) gösterilmez; hangi cümlenin hangi kaynaktan
geldiği yalnızca stderr'e dim olarak yazılır (geliştirici logu).

Not: SSL sertifika doğrulaması bu ortamda başarısız olduğu için
verify=False kullanılıyor. Production'da True yapılması önerilir.
"""

import sys
import time

# Windows konsolu varsayılan olarak cp1254/cp437; Türkçe karakterler ve
# Unicode simgeler için bozulur. UTF-8'a zorla — encoding hatası olursa
# (örn. eski Windows) program yine de çalışsın diye try/except ile sarıyoruz.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from content_filter import check_content, is_locked, lock_session
from ranker import mmr_select
from scraper import (
    extract_main_text,
    fetch_page,
    pick_relevant_sentences_scored,
)
from search_engine import search


# Arama motorundan istenen sonuç sayısı
SEARCH_MAX_RESULTS = 6
# Kaynak başına TextRank'tan istenen en fazla cümle (scraper.py kendi içinde
# metin uzunluğuna göre 2/4/5 cap'iyle kırpar).
PER_SOURCE_SENTENCES = 5
# Yanıt panelinde gösterilecek toplam en fazla cümle — global cross-source
# sıralama + dedupe sonrası uygulanır.
MAX_ANSWER_SENTENCES = 5
# SSL doğrulaması: bu ortamda False gerekli
VERIFY_SSL = False

# Çıkış komutları (küçük harf + boşluk temizliği ile karşılaştırılır)
EXIT_COMMANDS = frozenset({"çıkış", "exit", "q", "quit"})

# Tek seferlik başlangıç uyarısı (verify=False için)
_STARTUP_WARNING_SHOWN = False

# Kullanıcıya dönük tek Console — renk, panel, canlı spinner buradan
_console = Console()
# Geliştirici logları için ayrı stderr Console — per-sentence provenance
# buraya yazılır; stdout'a sızmaz
_err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Yardımcı UI fonksiyonları
# ---------------------------------------------------------------------------

def _render_header(query: str) -> None:
    """Sorgu başlığını ince bir panel olarak yazdırır."""
    _console.print(
        Panel(
            Text(query, style="bold"),
            title="[bold cyan]Arama[/bold cyan]",
            title_align="left",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _render_footer(elapsed: float) -> None:
    """Süre bilgisini dim satır olarak yazdırır (Claude Code stili)."""
    # › (U+203A) evrensel olarak güvenli; ⏱ (U+23F1) eski Windows
    # konsollarında UnicodeEncodeError verir.
    _console.print(f"[dim]› {elapsed:.1f} saniyede tamamlandı[/dim]")


def _render_locked_panel() -> None:
    """Kilitli oturum mesajını kırmızı panel olarak yazdırır."""
    body = Text()
    body.append("Bu oturum kalıcı olarak kilitlendi.\n", style="bold red")
    body.append(
        "Program kapatılıp yeniden açılsa bile bu mesaj görünecek.\n"
        "Kilidi kaldırmak için [bold]lock.txt[/bold] dosyasını silin.",
        style="dim",
    )
    _console.print(
        Panel(body, border_style="red", padding=(1, 2), title="Kilitli")
    )


def _render_forbidden_panel(matched: str) -> None:
    """Yasaklı içerik tespit edildiğinde sarı uyarı paneli."""
    body = Text()
    body.append("Bu tür sorulara cevap veremiyorum.\n", style="bold yellow")
    body.append("Tespit edilen uygunsuz içerik: ", style="dim")
    body.append(f"'{matched}'", style="bold yellow")
    _console.print(
        Panel(
            body,
            border_style="yellow",
            padding=(1, 2),
            title="İçerik engellendi",
        )
    )


def _render_lock_notice() -> None:
    """Kilit uyarısını kısa dim paragraf olarak yazdırır (kilitlendikten sonra)."""
    _console.print(
        "[dim]Bu oturum artık kilitlendi. Program kapatılsa bile tekrar açıldığında çalışmayacak.[/dim]"
    )


def _render_no_results_panel() -> None:
    """Hiç kaynak gelmediğinde tek bilgi paneli."""
    body = Text("Hiçbir kaynaktan kullanılabilecek bilgi alınamadı.\n", style="bold")
    body.append(
        "Hedef siteler scraping'e izin vermiyor, internet bağlantısı kesilmiş "
        "veya sorgu çok özel olabilir — farklı kelime deneyin.",
        style="dim",
    )
    _console.print(Panel(body, border_style="yellow", padding=(1, 2)))


def _render_answer_panel(sentences: list[str]) -> None:
    """Birleştirilmiş yanıtı tek panelde, satır satır, bulletsız yazdırır."""
    body = Text()
    for sentence in sentences:
        body.append(sentence)
        body.append("\n\n")
    _console.print(
        Panel(
            body,
            title="[bold]Yanıt[/bold]",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Lock + startup helpers
# ---------------------------------------------------------------------------

def _print_startup_warning() -> None:
    """SSL verify=False kullanıldığını belirten tek seferlik uyarı."""
    global _STARTUP_WARNING_SHOWN
    if _STARTUP_WARNING_SHOWN:
        return
    _STARTUP_WARNING_SHOWN = True
    _console.print(
        Panel(
            "[dim]SSL sertifika doğrulaması devre dışı (verify=False). "
            "Bu, bu ortamda DuckDuckGo'ya erişim için zorunlu. "
            "Kodu production'a alırken [bold]main.py[/bold] içindeki "
            "[bold]VERIFY_SSL = True[/bold] yapın.[/dim]",
            border_style="dim",
            padding=(0, 2),
        )
    )


def _handle_locked_state() -> bool:
    """Program açılışında kilit dosyasını kontrol eder; kilitliyse panel yazdırır."""
    if is_locked():
        _render_locked_panel()
        return True
    return False


def _handle_user_query() -> str | None:
    """Kullanıcıdan soru alır.

    Dönüş:
        ""  -> kullanıcı sadece Enter'a bastı; döngü yeniden sormalı
        str -> geçerli sorgu
        None -> Ctrl+C / EOF; program temiz çıkış yapmalı
    """
    _console.print(
        "[bold cyan]Sorunuzu veya aramak istediğiniz kelimeyi yazın[/bold cyan]"
    )
    _console.print(
        "[dim]İpucu: çıkmak için 'q', 'exit' veya 'çıkış' yazın; "
        "iptal için Ctrl+C.[/dim]"
    )
    try:
        query = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        _console.print("\n[dim]Çıkılıyor.[/dim]")
        return None
    if not query:
        _console.print(
            "[dim]Boş soru, yeniden deneyin veya çıkmak için 'q' yazın.[/dim]"
        )
        return ""
    return query


# ---------------------------------------------------------------------------
# Cross-source sıralama + dedupe
# ---------------------------------------------------------------------------

def _normalize_for_dedupe(sentence: str) -> str:
    """Dedupe anahtarı: küçük harf + tüm boşlukları tek boşluk. Noktalama
    bırakılır — aynı cümlenin farklı sondan-trimli versiyonlarını yakalar.
    """
    return " ".join(sentence.casefold().split())


def _run_search_and_collect(query: str) -> list[dict]:
    """
    Arama + scraping + iki aşamalı cümle seçimi (TextRank → MMR).

    Aşamalar:
      1. DuckDuckGo araması
      2. Her sonuç için sayfa çek + temizle + TextRank ile 2-5 aday cümle
      3. (yeni) MMR ile adayları küresel olarak sırala: sorgu alakalılığı
         + önceden seçilenlerle düşük benzerlik → en fazla MAX_ANSWER_SENTENCES
         cümle, en alakalıdan en az alakalıya.

    Spinner + per-source durum metni önceki planla aynı; dönüş şekli de
    aynı (kaynak ayrımı yok). Tek fark: cümleler artık MMR sırasıyla
    döner, küresel TextRank skoruna göre değil.

    Dönüş: [
        {"sentence": str, "score": float, "source_url": str, "source_title": str},
        ...
    ]
    """
    candidates: list[dict] = []
    skipped = 0

    with Live(
        Spinner("dots", text=Text("Aranıyor…", style="cyan")),
        console=_console,
        transient=True,
        refresh_per_second=12,
    ) as live:

        def update_status(message: str) -> None:
            live.update(Spinner("dots", text=Text(message, style="cyan")))

        # 1) DuckDuckGo araması
        results = search(query, max_results=SEARCH_MAX_RESULTS, verify_ssl=VERIFY_SSL)
        if not results:
            update_status("Arama sonucu bulunamadı")
            time.sleep(0.4)
            return []

        total = len(results)
        update_status(f"{total} kaynak taranıyor…")

        # 2) Her sonucu çek, temizle, scored picks al → aday havuzuna ekle
        for i, r in enumerate(results, 1):
            url = r["href"]
            title = r["title"]

            short_url = url if len(url) <= 55 else url[:52] + "…"
            update_status(f"{i}/{total} — {short_url}")

            html = fetch_page(url, verify_ssl=VERIFY_SSL)
            if html is None:
                skipped += 1
                continue

            text = extract_main_text(html)
            if not text:
                skipped += 1
                continue

            # Scored picks — scraper kendi length cap'iyle (2/4/5) sınırlar
            scored = pick_relevant_sentences_scored(
                text, query, max_sentences=PER_SOURCE_SENTENCES
            )
            if not scored:
                skipped += 1
                continue

            for score, sentence in scored:
                candidates.append({
                    "sentence": sentence,
                    "score": score,
                    "source_url": url,
                    "source_title": title,
                })

        # 3) Cross-source: önce birebir aynı cümleleri çıkar (kesin
        # dedupe), sonra MMR'a devret. MMR cosine ile yakın cümleleri
        # ayrıca eleyecek.
        seen: set[str] = set()
        unique: list[dict] = []
        for c in candidates:
            key = _normalize_for_dedupe(c["sentence"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)

        deduped = mmr_select(
            query=query,
            candidates=unique,
            top_k=MAX_ANSWER_SENTENCES,
            lambda_=0.65,
        )

        # Spinner kapanmadan önce son özet
        if skipped:
            update_status(
                f"{total - skipped}/{total} kaynaktan bilgi alındı · "
                f"{skipped} atlandı · {len(deduped)} cümle seçildi"
            )
        else:
            update_status(
                f"{total}/{total} kaynaktan bilgi alındı · {len(deduped)} cümle seçildi"
            )
        time.sleep(0.3)

    return deduped


# ---------------------------------------------------------------------------
# Sonuç render
# ---------------------------------------------------------------------------

def _display_results(query: str, candidates: list[dict]) -> None:
    """Yanıt panelini yazdırır ve provenance'ı stderr'e yazar."""
    _render_header(query)

    if not candidates:
        _render_no_results_panel()
        return

    sentences = [c["sentence"] for c in candidates]
    _render_answer_panel(sentences)

    # Geliştirici logu: her cümlenin hangi kaynaktan geldiği (stdout'a sızmaz)
    for i, c in enumerate(candidates, 1):
        _err_console.print(
            f"[dim][{i}/{len(candidates)}] {c['source_url']}[/dim]"
        )


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------

def _process_query(query: str) -> bool:
    """Tek bir sorguyu işler.

    Dönüş:
        True  -> program çıkmalı (yasaklı içerik kilitledi)
        False -> döngü devam etmeli
    """
    # İçerik kontrolü
    is_bad, matched = check_content(query)
    if is_bad:
        _render_forbidden_panel(matched or "")
        lock_session(f"yasaklı kelime tespit edildi: {matched}")
        _render_lock_notice()
        return True

    start = time.perf_counter()
    candidates = _run_search_and_collect(query)
    elapsed = time.perf_counter() - start

    _display_results(query, candidates)
    _render_footer(elapsed)

    return False


def main() -> int:
    """Ana giriş noktası — REPL."""
    _print_startup_warning()

    # 1. Kilit kontrolü
    if _handle_locked_state():
        return 1

    # 2. Sorgu döngüsü
    while True:
        query = _handle_user_query()

        # Ctrl+C / EOF → temiz çıkış
        if query is None:
            return 0

        # Boş giriş → yeniden sor
        if not query:
            continue

        # Çıkış komutu → veda
        if query.casefold() in EXIT_COMMANDS:
            _console.print("[dim]Görüşürüz.[/dim]")
            return 0

        # Sorguyu işle
        if _process_query(query):
            return 1


if __name__ == "__main__":
    sys.exit(main())
