#!/usr/bin/env python3

import unittest

from scripts.transliteration import transliterate_gurmukhi


class TransliterationTests(unittest.TestCase):
    def test_mool_mantar_opening(self):
        self.assertEqual(
            transliterate_gurmukhi("ੴ ਸਤਿ ਨਾਮੁ ਕਰਤਾ ਪੁਰਖੁ"),
            "ikOankaar sat naam karataa purakh",
        )

    def test_basic_line_with_markers(self):
        self.assertEqual(
            transliterate_gurmukhi("॥ ਜਪੁ ॥"),
            "|| jap ||",
        )

    def test_nasalization_and_digits(self):
        self.assertEqual(
            transliterate_gurmukhi("ਸੈਭੰ ਗੁਰ ਪ੍ਰਸਾਦਿ ॥੧॥"),
            "saibha(n) gur prasaad ||1||",
        )

    def test_final_ai_and_au_are_preserved(self):
        self.assertEqual(
            transliterate_gurmukhi("ਨਿਰਭਉ ਨਿਰਵੈਰੁ"),
            "nirabhau niravair",
        )

    def test_source_punctuation_noise_is_removed(self):
        self.assertEqual(
            transliterate_gurmukhi("ਸੋਚੈ. ਸੋਚਿ ਨ ਹੋਵਈ; ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ ॥"),
            "sochai soch na hovaee je sochee lakh vaar ||",
        )

    def test_terminal_u_endings_are_preserved(self):
        self.assertEqual(transliterate_gurmukhi("ਕਰਹੁ"), "karahu")
        self.assertEqual(transliterate_gurmukhi("ਹੋਹੁ"), "hohu")
        self.assertEqual(transliterate_gurmukhi("ਰਹੁ"), "rahu")
        self.assertEqual(transliterate_gurmukhi("ਕਹੁ"), "kahu")
        self.assertEqual(
            transliterate_gurmukhi("ਨਾਨਕ ਚਿੰਤਾ ਮਤਿ ਕਰਹੁ ਚਿੰਤਾ ਤਿਸ ਹੀ ਹੇਇ ॥"),
            "naanak chi(n)taa mat karahu chi(n)taa tis hee hei ||",
        )

    def test_terminal_i_endings_are_preserved(self):
        self.assertEqual(transliterate_gurmukhi("ਕਰਹਿ"), "karahi")
        self.assertEqual(transliterate_gurmukhi("ਮਰਹਿ"), "marahi")
        self.assertEqual(transliterate_gurmukhi("ਗਾਵਹਿ"), "gaavahi")
        self.assertEqual(
            transliterate_gurmukhi("ਵਾਹੁ ਵਾਹੁ ਗੁਰਮੁਖ ਸਦਾ ਕਰਹਿ ਮਨਮੁਖ ਮਰਹਿ ਬਿਖੁ ਖਾਇ ॥"),
            "vaahu vaahu guramukh sadaa karahi manamukh marahi bikh khaai ||",
        )

    def test_non_hi_terminal_i_is_still_stripped(self):
        # Terminal -i on non-ਹ stems remains a pronunciation strip (common
        # nominative / oblique suffix). Guard is narrow to ਹਿ only.
        self.assertEqual(transliterate_gurmukhi("ਸਤਿ"), "sat")
        self.assertEqual(transliterate_gurmukhi("ਪ੍ਰਸਾਦਿ"), "prasaad")

    def test_gurmukhi_sign_yakash_is_transliterated(self):
        self.assertEqual(transliterate_gurmukhi("ਕਲੵਾਨਾ"), "kalyaanaa")
        self.assertEqual(transliterate_gurmukhi("ਗੵਾਨ"), "gyaan")
        self.assertEqual(transliterate_gurmukhi("ਧੵਾਨ"), "dhyaan")
        self.assertEqual(transliterate_gurmukhi("ਅੰਧੵਾਰ"), "a(n)dhyaar")

    def test_gurmukhi_sign_udaat_is_transliterated(self):
        self.assertEqual(transliterate_gurmukhi("ਜਿਨੑ"), "jinh")
        self.assertEqual(transliterate_gurmukhi("ਤੁਮੑ"), "tumh")
        self.assertEqual(transliterate_gurmukhi("ਕਾਲੑਿ"), "kaalhi")
        self.assertEqual(transliterate_gurmukhi("ਲੁੜੑੰਦੜੀ"), "luRh(n)daRee")

    def test_adak_bindi_and_joiners_are_normalized(self):
        self.assertEqual(transliterate_gurmukhi("ਕੁੜੀਁ"), "kuRee(n)")
        self.assertEqual(transliterate_gurmukhi("ਭਾਵਂ‍ੀ"), "bhaava(n)ee")
        self.assertEqual(transliterate_gurmukhi("ਥੁੜਂ‍ੀਦੋ"), "thuRa(n)eedo")


if __name__ == "__main__":
    unittest.main()
