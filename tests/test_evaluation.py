from cte442_asr.evaluation import normalize_text, score, sentence_length_bucket


def test_word_and_character_error_rates():
    result = score("Hello, Lagos world", "hello lagos")
    assert result["deletions"] == 1
    assert result["error_rate"] == 1 / 3
    assert score("abc", "adc", "char")["error_rate"] == 1 / 3


def test_normalization_and_lengths():
    assert normalize_text("  It's—OK! ") == "it's ok"
    assert sentence_length_bucket("one two three") == "short_1_5"
    assert sentence_length_bucket("one two three four five six") == "medium_6_12"
    assert sentence_length_bucket(" ".join(["x"] * 13)) == "long_13_plus"

