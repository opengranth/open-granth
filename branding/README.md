# Open Granth Brand Assets

## The mark

The wordmark is "Open Granth" followed by a trailing double danda (॥, U+0965), known in Gurmukhi as doḍaṇḍī (ਦੋਡੰਡੀ). The mark is not decorative: it is used throughout Sri Guru Granth Sahib Ji to mark verse boundaries. Placing it here signals what this project is: a source-derived digital presentation of the Granth, without any additional explanation.

## Fonts

**Wordmark:** EB Garamond, a free and open revival of Claude Garamond's sixteenth-century types.

Weight decision: split by context.
- **400 (display)**: `wordmark.svg`, `wordmark-inverse.svg`, `wordmark-onecolour.svg`. At headline sizes the lighter weight has more refined stroke contrast and sharper serifs; it reads like a scholarly title.
- **500 (small)**: `wordmark-small.svg`. At nav-bar and GitHub repo-header scales (150px and below), the slightly heavier strokes hold better without breaking up.

**Double danda (॥):** Noto Serif Gurmukhi 400. The double danda is sized at 0.8em relative to the Latin cap height, baseline-aligned, with a gap of 0.256em from the final Latin glyph.

Letter-spacing: 0.005em applied uniformly across the Latin glyphs.

## Palette

| Name | Hex | Use |
|------|-----|-----|
| Ink | `#201f1d` | Primary text on paper |
| Paper | `#f3f2f2` | Background; text on ink grounds |
| Ink ground | `#2d2b2b` | Dark background variant |
| Gold | `#b68235` | Double danda on paper |
| Gold lifted | `#e1ad66` | Double danda on ink grounds (lifted for contrast) |

## Usage rules

- **Clear space:** maintain a minimum clear space equal to the double danda height on all sides of the wordmark.
- **Below 20px:** the double danda renders in paper-white on an ink ground. The higher-contrast treatment is visibly crisper than gold at the smallest delivered size.
- **16px favicon:** use a full-bleed ink ground with an optically enlarged paper-white double danda. Hairline borders do not survive reliably at this size.
- **32px and above:** use the full-bleed ink ground with an optically enlarged lifted-gold double danda.
- **Browser delivery:** pages declare explicit 16px and 32px PNG favicons, followed by the combined ICO fallback. This preserves the size-specific colour decision; a single scalable favicon cannot reliably infer its rendered size.
- **Never substitute the double danda.** Do not approximate ॥ with ASCII pipes (||), vertical bars, or any other character. The glyph must come from a Gurmukhi font.
- **Never use the Khanda or Ik Onkar (ੴ) in branding.** Open Granth reserves the Khanda and Ik Onkar for sacred or devotional contexts rather than using them as brand marks. This project uses the double danda because it belongs to the text itself, not to the faith's iconography.

## File inventory

### SVGs (deterministic, shaped from real fonts)

| File | Description |
|------|-------------|
| `wordmark.svg` | Display weight (400), ink on transparent |
| `wordmark-inverse.svg` | Display weight (400), paper text, for use on ink grounds |
| `wordmark-onecolour.svg` | Display weight (400), single ink colour |
| `wordmark-small.svg` | Small weight (500), ink on transparent, for nav bars and small headers |
| `device-paper.svg` | Boxed device, 112×112, hairline ink border, gold double danda |
| `device-ink.svg` | Full-bleed device, 112×112, ink-ground fill, optically enlarged lifted-gold double danda |
| `device-onecolour.svg` | Boxed device, 112×112, single ink colour |
| `favicon-16.svg` | Device at 16px spec: full-bleed ink ground and optically enlarged paper-white double danda |
| `favicon.svg` | Alias of `favicon-16.svg`, retained as the scalable source and fallback asset |

### Rasters

| File | Dimensions | Description |
|------|-----------|-------------|
| `favicon-16.png` | 16×16 | Full-bleed ink device with paper-white double danda |
| `favicon-32.png` | 32×32 | Full-bleed ink device with lifted-gold double danda |
| `favicon.ico` | 16+32 combined | Browser favicon (ICO container) |
| `apple-touch-icon.png` | 180×180 | Full-bleed ink device with optically enlarged lifted-gold double danda |
| `social-card.png` | 1200×630 | Centered paper-ground wordmark with the timeless project line and canonical domain |
