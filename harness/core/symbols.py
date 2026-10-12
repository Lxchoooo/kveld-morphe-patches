"""
Obfuscated Symbol Resolver and Structural Equivalence Verification Engine.
Deterministically identifies obfuscated method and field renames across Brave browser updates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from harness.core.dex import DexIndex, IndexedClass, IndexedMethod


class SymbolConfidence(str, Enum):
    VERIFIED = "VERIFIED"
    HIGH = "HIGH"
    LOW = "LOW"
    BLOCKED = "BLOCKED"


@dataclass
class ResolvedSymbol:
    symbol_id: str
    target_class: str
    old_symbol: str
    new_symbol: str
    symbol_type: str  # 'field', 'method', 'signature'
    confidence: SymbolConfidence
    evidence: List[str] = field(default_factory=list)


@dataclass
class BraveOriginSymbols:
    locked_field: ResolvedSymbol
    key_mapping_method: ResolvedSymbol
    context_getter_method: ResolvedSymbol
    update_prefs_method: ResolvedSymbol
    find_pref_method: ResolvedSymbol
    pref_listener_field: ResolvedSymbol
    pref_key_field: ResolvedSymbol = field(default_factory=lambda: ResolvedSymbol(
        symbol_id="origin_pref_key_field",
        target_class="Landroidx/preference/Preference;",
        old_symbol="G:Ljava/lang/String;",
        new_symbol="G:Ljava/lang/String;",
        symbol_type="field",
        confidence=SymbolConfidence.VERIFIED,
        evidence=["Resolved Preference key field"]
    ))


@dataclass
class BraveNotificationSchedulerSymbols:
    on_start_task_method: ResolvedSymbol


class SymbolResolver:
    """Resolves obfuscated members on Brave classes using structural analysis."""

    def __init__(self, index: DexIndex):
        self.index = index

    def resolve_all(self) -> Dict[str, Any]:
        return {
            "origin": self.resolve_brave_origin_symbols(),
            "scheduler": self.resolve_notification_scheduler_symbols(),
        }

    def resolve_brave_origin_symbols(self) -> Optional[BraveOriginSymbols]:
        cls_name = "Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;"
        cls = self.index.find_class(cls_name)
        if not cls:
            return None

        # Validate onPreferenceChange method signature
        if not self._has_on_preference_change(cls):
            return None

        hierarchy_methods = cls.get_all_hierarchy_methods(self.index)
        return BraveOriginSymbols(
            locked_field=self._resolve_origin_locked_field(cls, cls_name),
            key_mapping_method=self._resolve_origin_key_mapping(cls, cls_name),
            context_getter_method=self._resolve_origin_context_getter(hierarchy_methods, cls_name),
            update_prefs_method=self._resolve_origin_update_prefs(cls, cls_name),
            find_pref_method=self._resolve_origin_find_pref(hierarchy_methods, cls_name),
            pref_listener_field=self._resolve_origin_pref_listener(),
            pref_key_field=self._resolve_origin_pref_key(cls),
        )

    @staticmethod
    def _has_on_preference_change(cls: IndexedClass) -> bool:
        return any(
            m.return_type == "Z" and len(m.parameters) in (1, 2) and
            m.parameters[0] == "Landroidx/preference/Preference;"
            for m in cls.methods
        )

    @staticmethod
    def _resolve_origin_locked_field(cls: IndexedClass, cls_name: str) -> ResolvedSymbol:
        boolean_fields = [f for f in cls.fields if f[1] == "Z" and (f[2] & 0x8) == 0]
        # A settings class normally holds several instance booleans. Taking the first one
        # is a guess, and the migrator writes that name straight into BraveOriginPatch.kt,
        # so an ambiguous match must block instead of being reported as verified.
        ambiguous = len(boolean_fields) > 1
        locked_field_name = boolean_fields[0][0] if boolean_fields else "O0"
        evidence = (
            [f"Instance boolean field on {cls_name}: {locked_field_name}"]
            if boolean_fields and not ambiguous
            else [
                f"{len(boolean_fields)} instance boolean field(s) on {cls_name} "
                f"({', '.join(f[0] for f in boolean_fields[:6])}); the locked one is ambiguous"
            ]
        )
        return ResolvedSymbol(
            symbol_id="origin_locked_field",
            target_class=cls_name,
            old_symbol="N0:Z",
            new_symbol=f"{locked_field_name}:Z",
            symbol_type="field",
            confidence=(
                SymbolConfidence.VERIFIED
                if boolean_fields and not ambiguous
                else SymbolConfidence.BLOCKED
            ),
            evidence=evidence
        )

    @staticmethod
    def _resolve_origin_key_mapping(cls: IndexedClass, cls_name: str) -> ResolvedSymbol:
        static_str_str = [
            m for m in cls.methods
            if (m.access_flags & 0x8) != 0 and m.parameters == ["Ljava/lang/String;"] and m.return_type == "Ljava/lang/String;"
        ]
        # Same rule as the locked field: several static String->String helpers can coexist,
        # and writing the wrong one into the patch would rewrite an unrelated call site.
        ambiguous = len(static_str_str) > 1
        key_map_name = static_str_str[0].name if static_str_str else "e5"
        evidence = (
            [f"Static (String) -> String method on {cls_name}: {key_map_name}"]
            if static_str_str and not ambiguous
            else [
                f"{len(static_str_str)} static (String)->String method(s) on {cls_name} "
                f"({', '.join(m.name for m in static_str_str[:6])}); the key mapping one is ambiguous"
            ]
        )
        return ResolvedSymbol(
            symbol_id="origin_key_mapping_method",
            target_class=cls_name,
            old_symbol="b5(Ljava/lang/String;)Ljava/lang/String;",
            new_symbol=f"{key_map_name}(Ljava/lang/String;)Ljava/lang/String;",
            symbol_type="method",
            confidence=(
                SymbolConfidence.VERIFIED
                if static_str_str and not ambiguous
                else SymbolConfidence.BLOCKED
            ),
            evidence=evidence
        )

    @staticmethod
    def _resolve_origin_context_getter(hierarchy_methods: List[IndexedMethod], cls_name: str) -> ResolvedSymbol:
        context_getters = [
            m for m in hierarchy_methods
            if (m.access_flags & 0x8) == 0 and len(m.parameters) == 0 and m.return_type == "Landroid/content/Context;"
        ]
        ambiguous = len(context_getters) > 1
        ctx_name = context_getters[0].name if context_getters else "N3"
        return ResolvedSymbol(
            symbol_id="origin_context_getter_method",
            target_class=cls_name,
            old_symbol="B4()Landroid/content/Context;",
            new_symbol=f"{ctx_name}()Landroid/content/Context;",
            symbol_type="method",
            confidence=(
                SymbolConfidence.VERIFIED
                if context_getters and not ambiguous
                else SymbolConfidence.BLOCKED
            ),
            evidence=[f"Instance () -> Context method on {cls_name} (or superclass): {ctx_name}"]
            if context_getters and not ambiguous
            else [
                f"{len(context_getters)} instance () -> Context method(s) on {cls_name} "
                f"({', '.join(m.name for m in context_getters[:6])}); the context getter is ambiguous"
            ],
        )

    @staticmethod
    def _resolve_origin_update_prefs(cls: IndexedClass, cls_name: str) -> ResolvedSymbol:
        void_zero_param = [
            m for m in cls.methods
            if (m.access_flags & 0x8) == 0 and len(m.parameters) == 0 and m.return_type == "V" and m.name not in ("<init>", "onStart", "onResume")
        ]
        ambiguous = len(void_zero_param) > 1
        update_name = void_zero_param[0].name if void_zero_param else "d5"
        return ResolvedSymbol(
            symbol_id="origin_update_prefs_method",
            target_class=cls_name,
            old_symbol="e5()V",
            new_symbol=f"{update_name}()V",
            symbol_type="method",
            confidence=(
                SymbolConfidence.VERIFIED
                if void_zero_param and not ambiguous
                else SymbolConfidence.BLOCKED
            ),
            evidence=[f"Instance () -> V refresh method on {cls_name}: {update_name}"]
            if void_zero_param and not ambiguous
            else [
                f"{len(void_zero_param)} candidate refresh method(s) on {cls_name} "
                f"({', '.join(m.name for m in void_zero_param[:6])}); the update method is ambiguous"
            ],
        )

    @staticmethod
    def _resolve_origin_find_pref(hierarchy_methods: List[IndexedMethod], cls_name: str) -> ResolvedSymbol:
        find_pref_candidates = [
            m for m in hierarchy_methods
            if len(m.parameters) == 1 and m.parameters[0] == "Ljava/lang/CharSequence;" and m.return_type == "Landroidx/preference/Preference;"
        ]
        ambiguous = len(find_pref_candidates) > 1
        find_pref_name = find_pref_candidates[0].name if find_pref_candidates else "S4"
        return ResolvedSymbol(
            symbol_id="origin_find_pref_method",
            target_class=cls_name,
            old_symbol="P4(Ljava/lang/CharSequence;)Landroidx/preference/Preference;",
            new_symbol=f"{find_pref_name}(Ljava/lang/CharSequence;)Landroidx/preference/Preference;",
            symbol_type="method",
            confidence=(
                SymbolConfidence.VERIFIED
                if find_pref_candidates and not ambiguous
                else SymbolConfidence.BLOCKED
            ),
            evidence=[f"Method (CharSequence) -> Preference on {cls_name} (or superclass): {find_pref_name}"]
            if find_pref_candidates and not ambiguous
            else [
                f"{len(find_pref_candidates)} (CharSequence) -> Preference method(s) on {cls_name} "
                f"({', '.join(m.name for m in find_pref_candidates[:6])}); the finder is ambiguous"
            ],
        )

    def _resolve_origin_pref_listener(self) -> ResolvedSymbol:
        pref_cls = self.index.find_class("Landroidx/preference/Preference;")
        pref_listener_field = "y"
        if pref_cls:
            listener_fields = [
                f[0] for f in pref_cls.fields
                if f[1] in ("Landroidx/preference/Preference$OnPreferenceChangeListener;", "Landroidx/preference/Preference$c;")
            ]
            if listener_fields:
                pref_listener_field = listener_fields[0]

        # Previously this always reported VERIFIED, even when Preference was not
        # found at all and the hardcoded fallback was returned. A guess that is
        # labelled as verified gets written into BraveOriginPatch.kt unchecked.
        resolved = pref_cls is not None and pref_listener_field != "y"
        return ResolvedSymbol(
            symbol_id="origin_pref_listener_field",
            target_class="Landroidx/preference/Preference;",
            old_symbol="y",
            new_symbol=pref_listener_field,
            symbol_type="field",
            confidence=SymbolConfidence.VERIFIED if resolved else SymbolConfidence.BLOCKED,
            evidence=(
                [f"Reflection listener field on Preference: '{pref_listener_field}'"]
                if resolved
                else ["Preference class or its listener field was not found; fallback 'y' is a guess"]
            ),
        )

    @staticmethod
    def _resolve_origin_pref_key(cls: IndexedClass) -> ResolvedSymbol:
        # Collect every candidate instead of keeping the last one found: with more
        # than one candidate the choice is a guess, and a guessed field name that
        # does not block migration would be written straight into the patch source.
        candidates: List[str] = []
        for m in cls.methods:
            if m.return_type == "Z" and len(m.parameters) in (1, 2) and m.parameters[0] == "Landroidx/preference/Preference;":
                code = m.encoded_method.get_code()
                if code:
                    for ins in code.get_bc().get_instructions():
                        raw = str(ins)
                        if "iget-object" in raw and "Landroidx/preference/Preference;->" in raw and ":Ljava/lang/String;" in raw:
                            match = re.search(r"Landroidx/preference/Preference;->([A-Za-z0-9_]+):Ljava/lang/String;", raw)
                            if match and match.group(1) not in candidates:
                                candidates.append(match.group(1))
        unique = len(candidates) == 1
        key_field = candidates[0] if candidates else "G"
        return ResolvedSymbol(
            symbol_id="origin_pref_key_field",
            target_class="Landroidx/preference/Preference;",
            old_symbol="G:Ljava/lang/String;",
            new_symbol=f"{key_field}:Ljava/lang/String;",
            symbol_type="field",
            confidence=SymbolConfidence.VERIFIED if unique else SymbolConfidence.BLOCKED,
            evidence=(
                [f"Preference key field resolved as '{key_field}'"]
                if unique
                else [
                    f"{len(candidates)} preference key field candidate(s) ({', '.join(candidates[:6])}); "
                    "the key field is ambiguous"
                ]
            ),
        )

    def resolve_notification_scheduler_symbols(self) -> Optional[BraveNotificationSchedulerSymbols]:
        cls_name = "Lorg/chromium/chrome/browser/notifications/scheduler/NotificationSchedulerTask;"
        cls = self.index.find_class(cls_name)
        if not cls:
            return None

        # onStartTask: returns I, first parameter is Context. Must be unique to be trusted.
        task_methods = [
            m for m in cls.methods
            if m.return_type == "I" and m.parameters[:1] == ["Landroid/content/Context;"]
        ]
        if len(task_methods) != 1:
            return None

        m = task_methods[0]
        sym = ResolvedSymbol(
            symbol_id="scheduler_on_start_task",
            target_class=cls_name,
            old_symbol="c",
            new_symbol=m.name,
            symbol_type="method",
            confidence=SymbolConfidence.VERIFIED,
            evidence=[f"NotificationScheduler task starter: {m.full_name}"]
        )
        return BraveNotificationSchedulerSymbols(on_start_task_method=sym)
