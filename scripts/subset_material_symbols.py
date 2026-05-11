"""Subset de la police Material Symbols Outlined.

Réduit la police variable de ~3,9 MB à quelques dizaines de Ko en ne gardant
que les icônes effectivement utilisées dans les templates du projet.

Usage:
    uv run python scripts/subset_material_symbols.py
"""
from __future__ import annotations

from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "app" / "static" / "fonts" / "MaterialSymbolsOutlined.woff2"
OUTPUT = ROOT / "app" / "static" / "fonts" / "MaterialSymbolsOutlined.woff2"

# Icônes utilisées dans le projet (toutes pages confondues).
# IMPORTANT : si tu ajoutes une nouvelle icône Material Symbols dans un
# template, ajoute-la ici puis relance le script.
ICONS = sorted({
    # Topbar / menu mobile
    "menu", "close", "home", "description", "dashboard",
    # Footer
    "public", "mail", "share",
    # Wizard toolbar + boutons
    "menu_book", "rocket_launch", "restart_alt",
    "add", "analytics", "picture_as_pdf", "arrow_forward",
    # Help / Deployment
    "arrow_back", "print",
    # Deployment guide (sections h2)
    "bolt", "checklist", "terminal", "verified", "tune",
    "build", "dns", "cloud", "shield", "build_circle",
    "support_agent",
    # Dashboard
    "open_in_new", "info",
    # Home / modules
    "schedule", "school", "construction", "check_circle",
    "account_balance_wallet", "sync_alt", "admin_panel_settings",
    "chevron_right",
    # Innovation Smart Mining
    "vrpano", "sensors",
})


def main() -> None:
    print(f"Police source : {INPUT}")
    print(f"Taille initiale : {INPUT.stat().st_size / 1024:.1f} Ko")
    print(f"Icônes à conserver ({len(ICONS)}) : {', '.join(ICONS)}")

    text = " ".join(ICONS)

    font = TTFont(str(INPUT))

    options = Options()
    options.flavor = "woff2"
    options.with_zopfli = False
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.glyph_names = True
    options.symbol_cmap = True
    options.legacy_cmap = False
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recommended_glyphs = True
    options.hinting = True
    options.desubroutinize = False

    subsetter = Subsetter(options=options)
    subsetter.populate(text=text)
    subsetter.subset(font)

    font.flavor = "woff2"
    font.save(str(OUTPUT))

    new_size = OUTPUT.stat().st_size
    print(f"Nouvelle taille : {new_size / 1024:.1f} Ko")
    print(f"Fichier sauvegardé : {OUTPUT}")


if __name__ == "__main__":
    main()
