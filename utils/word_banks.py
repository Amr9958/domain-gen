"""Word bank loading and saving helpers."""

from __future__ import annotations

import os
from typing import Dict, List

from constants import WORD_BANKS_DIR


DEFAULT_WORD_BANKS = {
    "abstract": ["nexus", "quantum", "vertex", "prime", "zenith", "arc", "flux", "core", "omni", "nova",
                 "cipher", "echo", "orbit", "axiom", "rune", "lumen", "ether", "apex", "aeon", "epoch"],
    "power": ["boost", "pro", "master", "elite", "ultra", "max", "hyper", "mega", "titan", "force",
              "surge", "drive", "grand", "super", "grip", "iron", "steel", "bold", "hero", "epic",
              "citadel", "vanguard", "forge", "kinetic", "ascend"],
    "tech": ["logic", "code", "dev", "sys", "net", "cloud", "ai", "stack", "bit", "data",
             "cyber", "tide", "link", "node", "sync", "byte", "bot", "hub", "web", "mesh",
             "deploy", "auth", "relay", "edge", "kern", "trace", "infra", "cache", "gpu", "api"],
    "finance": ["pay", "coin", "fund", "equity", "trust", "cap", "wealth", "asset", "fin", "cash",
                "credit", "vault", "trade", "hedge", "bond", "gold", "mint", "gain", "risk", "deal",
                "ledger", "quant", "yield", "pivot", "folio", "accord", "fiscal", "sterling", "rally", "merit"],
    "creative": ["spark", "mind", "vision", "art", "pixel", "canvas", "design", "studio", "craft", "muse",
                 "brush", "ink", "hue", "tone", "shade", "draw", "build", "fuse", "lumina", "dawn",
                 "palette", "glyph", "mosaic", "vivid", "atelier", "motif", "render", "quill", "neon", "prism"],
    "short_prefixes": ["my", "go", "up", "now", "pro", "try", "use", "top", "one", "new",
                       "max", "fly", "run", "zen", "pure", "true", "real", "wide", "open", "wise",
                       "bold", "calm", "cool", "clear", "fast", "smart", "ai", "io", "neo", "evo",
                       "zap", "vox", "rex", "duo", "arc", "hex", "jet", "leo", "ori", "rx"],
}


def ensure_word_banks_dir(base_path: str = WORD_BANKS_DIR) -> None:
    """Create the word bank directory when it does not exist yet."""
    os.makedirs(base_path, exist_ok=True)


def deduplicate_words(words: List[str]) -> List[str]:
    """Preserve order while removing duplicates."""
    return list(dict.fromkeys(words))


def load_word_banks(base_path: str = WORD_BANKS_DIR) -> Dict[str, List[str]]:
    """Load word banks from disk, creating default files when missing."""
    ensure_word_banks_dir(base_path)

    banks: Dict[str, List[str]] = {}
    for category, default_words in DEFAULT_WORD_BANKS.items():
        file_path = os.path.join(base_path, f"{category}.txt")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read().strip()
            if content:
                words = [word.strip().lower() for word in content.replace("\n", ",").split(",") if word.strip()]
                banks[category] = deduplicate_words(words)
            else:
                banks[category] = default_words
        else:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(", ".join(default_words))
            banks[category] = default_words

    return banks


def save_word_banks(banks: Dict[str, List[str]], base_path: str = WORD_BANKS_DIR) -> None:
    """Persist the current in-memory word banks to disk."""
    ensure_word_banks_dir(base_path)
    for category, words in banks.items():
        file_path = os.path.join(base_path, f"{category}.txt")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(", ".join(deduplicate_words(words)))
