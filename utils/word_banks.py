"""Word bank loading and saving helpers."""

from __future__ import annotations

import os
from typing import Dict, List

from constants import WORD_BANKS_DIR


DEFAULT_WORD_BANKS = {
    "common_modifiers": ["base", "core", "edge", "flow", "forge", "hub", "labs", "mesh", "nova", "pulse",
                         "stack", "vault", "works"],
    "premium_words": ["core", "nest", "mint", "vault", "apex", "prime", "nexus", "pulse", "shift", "edge"],
    "abstract": ["nexus", "quantum", "vertex", "prime", "zenith", "arc", "flux", "omni", "cipher", "echo",
                 "orbit", "axiom", "rune", "lumen", "ether", "aeon", "epoch"],
    "power": ["boost", "master", "elite", "titan", "force", "surge", "grand", "grip", "iron", "steel",
              "bold", "hero", "epic", "citadel", "vanguard", "kinetic", "ascend"],
    "tech": ["logic", "code", "dev", "sys", "net", "cloud", "ai", "bit", "data", "cyber",
             "link", "node", "byte", "bot", "web", "deploy", "auth", "relay", "kern", "trace",
             "infra", "cache", "gpu", "api", "saas", "pipeline", "runtime"],
    "finance": ["pay", "coin", "fund", "equity", "trust", "cap", "wealth", "asset", "fin", "cash",
                "credit", "trade", "hedge", "bond", "gold", "mint", "gain", "risk", "deal", "ledger",
                "quant", "yield", "folio", "fiscal", "sterling"],
    "commerce": ["brand", "cart", "catalog", "checkout", "commerce", "market", "merchant", "retail", "seller",
                 "shop", "store", "supply", "listing", "vendor", "fulfil", "dropship"],
    "travel": ["booking", "escape", "guide", "hotel", "journey", "local", "resort", "stay", "tour", "travel",
               "trip", "vista", "discover", "wander", "roam", "retreat", "getaway"],
    "health": ["care", "clinic", "doctor", "fit", "health", "med", "patient", "therapy", "well"],
    "property": ["broker", "estate", "home", "homes", "lease", "listing", "mortgage", "property", "realty",
                 "rental", "roof"],
    "education": ["academy", "class", "course", "learn", "lesson", "school", "skill", "study", "tutor"],
    "legal": ["advisor", "case", "compliance", "contract", "counsel", "legal", "pro", "tax"],
    "crypto": ["chain", "crypto", "dao", "defi", "protocol", "token", "wallet", "web3", "yield",
               "liquidity", "governance", "oracle", "bridge"],
    "brandable_fragments": ["aero", "arc", "atlas", "glyph", "halo", "luma", "mint", "nexa", "ora", "pixel",
                            "prism", "terra", "vector", "zen"],
    "short_prefixes": ["all", "one", "new", "max", "fly", "run", "tap", "pop", "zen", "pure",
                       "true", "real", "wide", "open", "wise", "bold", "calm", "cool", "clear", "sharp",
                       "fast", "smart", "neo", "evo", "zap", "vox", "rex", "duo", "arc", "hex",
                       "jet", "leo", "ori", "lux", "axi"],
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
