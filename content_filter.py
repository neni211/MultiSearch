"""
İçerik kontrolü ve oturum kilidi yönetimi.

- check_content(text): Yasaklı kelime listesine karşı kontrol eder.
  Eşleşme varsa (True, matched_word), yoksa (False, None) döner.
- is_locked(): lock.txt dosyası var mı kontrol eder.
- lock_session(reason): lock.txt dosyasını oluşturur (varsa üzerine yazar).
"""

import os
import re
from datetime import datetime

from banned_words import get_all_banned_words, _PUNCT_TO_REMOVE

# Kilit dosyası, programın çalıştığı dizinde oluşturulur
LOCK_FILE = "lock.txt"


def _normalize(text: str) -> str:
    """
    Metni karşılaştırma için normalleştirir:
    - küçük harfe çevirir
    - noktalama işaretlerini kaldırır
    - baştaki/sondaki boşlukları siler
    Türkçe karakterler korunur (lower() zaten locale-agnostic davranır).
    """
    text = text.lower()
    # Noktalama karakterlerini boşlukla değiştir, sonra fazla boşlukları sıkıştır
    for ch in _PUNCT_TO_REMOVE:
        text = text.replace(ch, " ")
    # Birden fazla boşluğu tek boşluğa indir
    text = " ".join(text.split())
    return text


def check_content(text: str) -> tuple[bool, str | None]:
    """
    Metni yasaklı kelimelere karşı kontrol eder.

    Dönüş:
        (True, matched_word)  -> eşleşme bulunduysa
        (False, None)         -> temizse

    Not: Kelime sınırı (\\b) kullanılarak substring false-positive'ler önlenir.
    Örneğin "mal" kelimesi ancak bağımsız bir kelime olarak geçtiğinde yakalanır;
    "normal", "formal" gibi kelimelerin içindeki "mal" eşleşmesi tetiklenmez.
    """
    if not text:
        return (False, None)
    normalized = _normalize(text)
    for word in get_all_banned_words().keys():
        word_norm = _normalize(word).strip()
        if not word_norm:
            continue
        # Word boundary ile ara: bağımsız kelime olmalı
        # Unicode word boundary \\b bazı Türkçe karakterlerle (ı, ğ, ş, ö, ü, ç, İ)
        # her zaman iyi çalışmaz; bu yüzden lookaround ile kontrol et:
        # sol/sağ tarafta kelime karakteri olmamalı
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(word_norm) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, normalized):
            return (True, word)
    return (False, None)


def is_locked() -> bool:
    """lock.txt dosyası varsa True, yoksa False döner."""
    return os.path.exists(LOCK_FILE)


def lock_session(reason: str) -> None:
    """
    lock.txt dosyasını nedeniyle birlikte oluşturur.
    Dosya zaten varsa üzerine yazar (günceller).
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    content = (
        "Bu oturum kalıcı olarak kilitlendi.\n"
        f"Kilitlenme zamanı: {timestamp}\n"
        f"Neden: {reason}\n"
    )
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def unlock() -> None:
    """Kilit dosyasını siler. Manuel müdahale için yardımcı fonksiyon."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)