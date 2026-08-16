"""
Open Granth v1 Release Gate: verify_gurbani

Frozen test corpus for regression testing. All tests must pass
before any release. Run from the repo root:

    .venv/bin/python tests/verify_release_gate.py

Expected result: 49/49 passed, 0 failed, RELEASE GATE: PASSED
"""

import sys

sys.path.insert(0, "mcp")
from server import verify_gurbani

passed = 0
failed = 0
total = 0


def test(cat, label, text, expected, script="auto", ang=None):
    global passed, failed, total
    total += 1
    r = verify_gurbani(text, script)
    s = r["status"]
    a = r.get("ang", "-")
    ok = s == expected
    if ang and ok and s == "verified":
        ok = a == ang
    if ok:
        passed += 1
        mark = "PASS"
    else:
        failed += 1
        mark = "FAIL"
    print(f"  [{mark}] {cat} | {label}: exp={expected} got={s} ang={a}")


print("=" * 60)
print("OPEN GRANTH v1 RELEASE GATE: verify_gurbani")
print("=" * 60)

# --- EXACT GURMUKHI ---
print("\n--- EXACT GURMUKHI ---")
test("Exact", "Repeated Mool Mantar", "ੴ ਸਤਿ ਨਾਮੁ ਕਰਤਾ ਪੁਰਖੁ ਨਿਰਭਉ ਨਿਰਵੈਰੁ ਅਕਾਲ ਮੂਰਤਿ ਅਜੂਨੀ ਸੈਭੰ ਗੁਰ ਪ੍ਰਸਾਦਿ", "partial_match")
test("Exact", "Japji", "ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ", "verified", ang=1)
test("Exact", "Kabeer nindaa", "ਨਿੰਦਉ ਨਿੰਦਉ ਮੋ ਕਉ ਲੋਗੁ ਨਿੰਦਉ", "verified", ang=339)
test("Exact", "Ang 70 muskal", "ਜਾ ਕਉ ਮੁਸਕਲੁ ਅਤਿ ਬਣੈ ਢੋਈ ਕੋਇ ਨ ਦੇਇ", "verified", ang=70)
test("Exact", "GTB salok 55", "ਸੰਗ ਸਖਾ ਸਭਿ ਤਜਿ ਗਏ ਕੋਊ ਨ ਨਿਬਹਿਓ ਸਾਥਿ", "verified", ang=1429)

# --- EXACT ENGLISH ---
print("\n--- EXACT ENGLISH ---")
test("ExactE", "Japji", "By thinking, He cannot be reduced to thought, even by thinking hundreds of thousands of times", "verified", ang=1)
test("ExactE", "Ang 70", "when your friends turn into enemies, and even your relatives have deserted you", "verified", ang=70)
test("ExactE", "Slanderer", "The slanderer is drowned, while I am carried across", "verified", ang=339)
test("ExactE", "Teri Tek", "With Your Support, I have no fear", "verified", ang=1147)

# --- PARTIAL GURMUKHI ---
print("\n--- PARTIAL GURMUKHI ---")
test("Partial", "bipat mai", "ਇਹ ਬਿਪਤਿ ਮੈ ਟੇਕ ਏਕ ਰਘੁਨਾਥ", "verified", ang=1429)
test("Partial", "Repeated tatee vaau", "ਲਗੈ ਨ ਤਤੀ ਵਾਉ", "partial_match")

# --- FAKE GURMUKHI ---
print("\n--- FAKE GURMUKHI ---")
test("FakeG", "Modern Punjabi", "ਵਾਹਿਗੁਰੂ ਜੀ ਨੇ ਕਿਹਾ ਕਿ ਸਾਰੇ ਧਰਮ ਬਰਾਬਰ ਹਨ", "not_found")
test("FakeG", "Political", "ਖਾਲਸਾ ਰਾਜ ਕਰੇਗਾ ਅਤੇ ਦੁਨੀਆ ਤੇ ਹਕੂਮਤ ਕਰੇਗਾ", "not_found")
test("FakeG", "Dietary", "ਗੁਰੂ ਸਾਹਿਬ ਨੇ ਕਿਹਾ ਮਾਸ ਖਾਣਾ ਪਾਪ ਹੈ", "not_found")
test("FakeG", "WhatsApp", "ਹਰ ਰੋਜ਼ ਸ਼ੁਕਰ ਕਰੋ ਪ੍ਰਭੂ ਦਾ ਤੁਹਾਡੇ ਤੇ ਮਿਹਰ ਹੈ", "not_found")

# --- FAKE ENGLISH ---
print("\n--- FAKE ENGLISH ---")
test("FakeE", "God everywhere", "God is everywhere and in everything", "not_found")
test("FakeE", "Ego enemy", "Ego is the enemy of the soul and must be destroyed", "not_found")
test("FakeE", "Hamburger", "The Lord blesses those who eat hamburgers with divine grace", "not_found")
test("FakeE", "Bitcoin", "Nanak says wealth accumulated through honest digital labor is blessed by the Lord", "not_found")
test("FakeE", "Khalsa branding", "The Khalsa shall rule the world and bring justice to all nations", "not_found")
test("FakeE", "Generic spiritual", "Meditate upon the divine light within your heart and find peace", "not_found")
test("FakeE", "Single common word", "God", "error")
test("FakeE", "Short common phrase", "divine grace", "error")

# --- OUTSIDE SGGS ---
print("\n--- OUTSIDE SGGS ---")
test("Outside", "Dasam Granth", "ਚੱਕ੍ਰ ਚਿਹਨ ਅਰੁ ਬਰਨ ਜਾਤਿ ਅਰੁ ਪਾਤਿ ਨਹਿਨ ਜਿਹ", "not_found")
test("Outside", "Sikh slogan", "ਬੋਲੇ ਸੋ ਨਿਹਾਲ ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "not_found")
test("Outside", "Instagram", "Trust in God timing everything happens for a reason", "not_found")

# --- MIXED ---
print("\n--- MIXED LANGUAGE ---")
test("Mixed", "Gurmukhi+English", "ਸੋਚੈ ਸੋਚਿ by thinking he cannot be reduced", "not_found")

# --- EDGE CASES ---
print("\n--- EDGE CASES ---")
test("Edge", "Empty", "", "error")
test("Edge", "Over 1000 chars", "x" * 1001, "error")
test("Edge", "Repeated Waheguru", "ਵਾਹਿਗੁਰੂ", "partial_match")
test("Edge", "Repeated Sat Naam", "ਸਤਿ ਨਾਮੁ", "partial_match")

# --- ALTERED AKHAR (subtle spelling corruption) ---
print("\n--- ALTERED AKHAR ---")
# Real verse: ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ; changed ਹੋਵਈ to ਹੋਵੈ (different vowel sign)
test("Altered", "Changed vowel sign", "ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵੈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ", "partial_match")
# Real verse: ਨਿੰਦਉ ਨਿੰਦਉ; swapped one ਉ for ਓ
test("Altered", "Swapped letter", "ਨਿੰਦੋ ਨਿੰਦਉ ਮੋ ਕਉ ਲੋਗੁ ਨਿੰਦਉ", "partial_match")
# Real verse but with words rearranged
# Rearranged words share character bigrams with the real verse,
# so partial_match is the honest answer (not verified, not not_found)
test("Altered", "Rearranged words", "ਲਖ ਵਾਰ ਸੋਚੀ ਜੇ ਨ ਹੋਵਈ ਸੋਚੈ ਸੋਚਿ", "partial_match")

# --- WRONG-ANG REGRESSION ---
print("\n--- WRONG-ANG REGRESSION ---")
# Verify that specific verses return the correct ang, not a wrong one
for text, expected_ang, label in [
    ("ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ", 1, "Japji must be Ang 1"),
    ("ਨਿੰਦਉ ਨਿੰਦਉ ਮੋ ਕਉ ਲੋਗੁ ਨਿੰਦਉ", 339, "Kabeer must be Ang 339"),
    ("ਜਾ ਕਉ ਮੁਸਕਲੁ ਅਤਿ ਬਣੈ ਢੋਈ ਕੋਇ ਨ ਦੇਇ", 70, "Muskal must be Ang 70"),
    ("ਸੰਗ ਸਖਾ ਸਭਿ ਤਜਿ ਗਏ ਕੋਊ ਨ ਨਿਬਹਿਓ ਸਾਥਿ", 1429, "GTB must be Ang 1429"),
    ("ਬੰਧਨ ਮਾਤ ਪਿਤਾ ਸੁਤ ਬਨਿਤਾ", 1147, "Bandhan must be Ang 1147"),
    ("ਤਾ ਤੂੰ ਸੁਖਿ ਸੋਉ ਹੋਇ ਅਚਿੰਤਾ", 176, "Sukh soau must be Ang 176"),
]:
    total += 1
    r = verify_gurbani(text)
    actual_ang = r.get("ang", "-")
    if r["status"] == "verified" and actual_ang == expected_ang:
        passed += 1
        print(f"  [PASS] WrongAng | {label}: ang={actual_ang}")
    else:
        failed += 1
        print(f"  [FAIL] WrongAng | {label}: expected ang={expected_ang}, got ang={actual_ang} status={r['status']}")

# --- TRANSLITERATION ---
print("\n--- TRANSLITERATION ---")
test("TransExact", "Exact translit", "sochai soch na hovaee je sochee lakh vaar", "verified", "transliteration", ang=1)
test("TransExact", "Repeated Mool Mantar translit", "ikOankaar sat naam karataa purakh nirabhau niravair", "partial_match", "transliteration")
# Slightly noisy: missing a vowel doubling
test("TransNoisy", "Noisy translit", "sochai soch na hovie je sochi lakh var", "not_found", "transliteration")
test("TransFake", "Fake translit", "mere dil khush hai prabhoo de naal sadaa khushi", "not_found", "transliteration")
test("TransFake", "Fake spiritual translit", "waheguru ji ne kaha sab dharam barabar han", "not_found", "transliteration")

# --- CITATION INTEGRITY ---
print("\n--- CITATION INTEGRITY ---")
for text, expected_ang in [
    ("ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ", 1),
    ("ਨਿੰਦਉ ਨਿੰਦਉ ਮੋ ਕਉ ਲੋਗੁ ਨਿੰਦਉ", 339),
    ("ਜਾ ਕਉ ਮੁਸਕਲੁ ਅਤਿ ਬਣੈ ਢੋਈ ਕੋਇ ਨ ਦੇਇ", 70),
    ("ਸੰਗ ਸਖਾ ਸਭਿ ਤਜਿ ਗਏ ਕੋਊ ਨ ਨਿਬਹਿਓ ਸਾਥਿ", 1429),
]:
    total += 1
    r = verify_gurbani(text)
    if r.get("ang") == expected_ang:
        passed += 1
        print(f"  [PASS] Citation | ang={expected_ang}")
    else:
        failed += 1
        print(f"  [FAIL] Citation | exp={expected_ang} got={r.get('ang', '-')}")

print()
print("=" * 60)
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
print("RELEASE GATE:", "PASSED" if failed == 0 else "FAILED")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
