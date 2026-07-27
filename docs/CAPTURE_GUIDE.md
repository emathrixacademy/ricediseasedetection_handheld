# Field Image Capture Guide

Guide for collecting a high-quality training dataset for the 6-class rice
disease/condition classifier.

## 1. General Capture Conditions

- **Lighting:** Diffuse daylight (overcast ideal). Avoid harsh midday shadows
  and direct sun glare on the leaf surface. Use the onboard LED as fill only.
- **Distance:** 15–25 cm from the leaf. Keep the target leaf filling ~60–80%
  of the frame.
- **Angle:** Sensor plane parallel to the leaf blade. Shoot both adaxial (top)
  and abaxial (underside) surfaces where lesions appear.
- **Leaf positioning:** Flatten the leaf against a neutral (matte, non-green)
  backing card to isolate it from background clutter.
- **Focus/stability:** Steady the handheld; confirm focus lock before capture.

## 2. Per-Class Capture Tips

| Class | What to capture |
|-------|-----------------|
| `healthy` | Uniform green, no lesions; various growth stages & varieties |
| `rice_blast` | Spindle-shaped lesions with gray centers, brown margins |
| `bacterial_leaf_blight` | Water-soaked yellow-white streaks from leaf tips/margins |
| `nitrogen_deficiency` | Uniform chlorosis (yellowing), older leaves first |
| `water_deficit` | Leaf rolling, wilting, tip drying; capture midday stress |
| `heat_stress` | Whitening/scorching of tips, sterility symptoms |

## 3. RGB vs NoIR Notes

- **RGB (CSI0):** Primary for lesion color/texture. Ensure accurate white
  balance.
- **NoIR (CSI1):** Captures NIR reflectance for NDVI/stress signals. Use a
  matched pair (RGB + NoIR of the *same* leaf) so fusion labels align.
- Capture RGB and NoIR back-to-back on the same target and store with matching
  session IDs.

## 4. Naming Convention

```
<class>_<varietyOrSite>_<YYYYMMDD>_<index>_<rgb|nir>.jpg
```
Example: `rice_blast_IR64_20260728_015_rgb.jpg`

## 5. How Many Images

Aim for **hundreds per class** (target ≥ 300, ideally 500+). Balance classes;
augmentation supplements but does not replace real field diversity across
varieties, sites, and lighting.

## 6. Folder Organization

```
training/dataset/raw/
├── healthy/
├── rice_blast/
├── bacterial_leaf_blight/
├── nitrogen_deficiency/
├── water_deficit/
└── heat_stress/
```
Keep RGB and NIR either in per-modality subfolders or suffix-tagged filenames
(see naming convention) within each class folder.
