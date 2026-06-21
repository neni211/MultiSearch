"""
Yasaklı kelime listesi.

Bu dosyayı düzenleyerek yeni yasaklı kelimeler ekleyebilir veya
mevcut olanları kaldırabilirsiniz. Sözlüklere yeni kelime eklemek için:

    BANNED_WORDS_TR["yeni_kelime"] = True
    BANNED_WORDS_EN["new_word"] = True

Karşılaştırma küçük harf ve noktalama temizliği yapıldıktan sonra
substring eşleşmesi ile yapılır; bu yüzden tek bir kelime olarak
kullanmak en güvenlisi.

Bu liste kasıtlı olarak kısa tutulmuştur — amacı kaba bir tarama.
İhtiyaca göre genişletin.
"""

# Türkçe yasaklı kelimeler
# Kategoriler: küfür/hakaret, cinsel içerik, şiddet, yasadışı maddeler
BANNED_WORDS_TR = {
    # küfür / hakaret
    "aptal": True,
    "salak": True,
    "gerizekalı": True,
    "mal": True,
    "orospu": True,
    "kahpe": True,
    "piç": True,
    "ibne": True,
    "amcık": True,
    "yarrak": True,
    "sik": True,
    "göt": True,
    "siktir": True,
    "amına": True,
    # şiddet
    "öldür": True,
    "öldürmek": True,
    "katletmek": True,
    "bomba": True,
    "silah": True,
    "terörizm": True,
    "teror": True,
    # cinsel içerik
    "porno": True,
    "pornografi": True,
    "seks": True,
    "fuhuş": True,
    # yasadışı
    "uyuşturucu": True,
    "eroin": True,
    "kokain": True,
    "esrar": True,
    "kaçakçılık": True,
    "hacklemek": True,
    "hackleme": True,
}

# İngilizce yasaklı kelimeler
BANNED_WORDS_EN = {
    # profanity / insults
    "fuck": True,
    "shit": True,
    "bitch": True,
    "asshole": True,
    "bastard": True,
    "cunt": True,
    "dick": True,
    "piss": True,
    # violence
    "kill": True,
    "murder": True,
    "bomb": True,
    "gun": True,
    "terrorism": True,
    "terrorist": True,
    # sexual
    "porn": True,
    "pornography": True,
    "sex": True,
    "prostitute": True,
    "prostitution": True,
    # illegal
    "drugs": True,
    "heroin": True,
    "cocaine": True,
    "marijuana": True,
    "smuggling": True,
    "hacking": True,
}

# Karakter temizliği için kullanılan karakterler (normalize edilecek)
_PUNCT_TO_REMOVE = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'


def get_all_banned_words():
    """TR + EN tüm yasaklı kelimelerin birleşik listesini döndürür."""
    return {**BANNED_WORDS_TR, **BANNED_WORDS_EN}