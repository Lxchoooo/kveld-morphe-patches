package com.kveld9.morphe.extension.gboard.i18n;

import java.util.Map;
import static com.kveld9.morphe.extension.gboard.GboardExtension.*;

public class FrLanguagePack extends BaseLanguagePack {
    @Override
    public String getLanguageCode() {
        return "fr";
    }

    @Override
    public String getLanguageName() {
        return "Français";
    }

    @Override
    public void populateTitles(Map<String, String> titles) {
        titles.put(PREF_KEY_HEADER, "Patchs Morphe");
        titles.put(PREF_KEY_SCREEN, "Patchs Morphe");
        titles.put(PREF_KEY_CAT_ACTIONS, "Actions et état");
        titles.put(PREF_KEY_ENABLE_IME, "Activer Gboard dans les paramètres système");
        titles.put(PREF_KEY_SELECT_IME, "Choisir Gboard comme clavier");
        titles.put(PREF_KEY_RESTART_GBOARD, "Redémarrer le processus Gboard");
        titles.put(PREF_KEY_CAT_APPEARANCE, "Apparence et thème");
        titles.put(PREF_KEY_AMOLED, "Thème AMOLED pur");
        titles.put(PREF_KEY_ZERO_BOTTOM_INSET, "Marge inférieure nulle");
        titles.put(PREF_KEY_BOTTOM_PADDING, "Marge intérieure basse (px)");
        titles.put(PREF_KEY_HIDE_IME_NAV_BAR, "Masquer la barre de navigation IME");
        titles.put(PREF_KEY_KEY_SHAPE_SELECTION, "Formes des touches");
        titles.put(PREF_KEY_EMOJI_SCALE, "Taille des émojis");
        titles.put(PREF_KEY_CAT_TOOLBAR, "Barre d'outils et navigation");
        titles.put(PREF_KEY_ACCESS_POINTS_REDESIGN, "Barre d'accès repensée");
        titles.put(PREF_KEY_TOOLBAR_ITEM_COUNT, "Nombre d'éléments de la barre");
        titles.put(PREF_KEY_DISMISS_SUGGESTIONS, "Bouton de fermeture des suggestions");
        titles.put(PREF_KEY_CURSOR_TRACKPAD, "Mode pavé tactile du curseur");
        titles.put(PREF_KEY_CAT_CLIPBOARD, "Presse-papiers");
        titles.put(PREF_KEY_CLIPBOARD_EXTENDED_RETENTION, "Conservation prolongée de l'historique");
        titles.put(PREF_KEY_CLIPBOARD_RETENTION_HOURS, "Durée de conservation (heures)");
        titles.put(PREF_KEY_CLIPBOARD_RAISE_LIMIT, "Augmenter la limite d'éléments non épinglés");
        titles.put(PREF_KEY_CLIPBOARD_UNPINNED_LIMIT, "Limite d'éléments non épinglés");
        titles.put(PREF_KEY_CLIPBOARD_GRID_LAYOUT, "Disposition en grille du presse-papiers");
        titles.put(PREF_KEY_CLIPBOARD_GRID_COLUMNS, "Colonnes de la grille du presse-papiers");
        titles.put(PREF_KEY_CLIPBOARD_CHAR_LIMIT, "Limite de caractères par élément");
        titles.put(PREF_KEY_CAT_HAPTICS, "Vibration et haptique");
        titles.put(PREF_KEY_DECOUPLE_TOUCH_FEEDBACK, "Vibration du clavier indépendante");
        titles.put(PREF_KEY_MODERN_HAPTICS, "Haptique moderne des touches");
        titles.put(PREF_KEY_CAT_SMART, "Fonctions intelligentes et voix");
        titles.put(PREF_KEY_GRAMMAR_CHECKER, "Correcteur grammatical et rédaction intelligente");
        titles.put(PREF_KEY_BLUETOOTH_MIC, "Micro Bluetooth");
        titles.put(PREF_KEY_CAT_PRIVACY, "Confidentialité et sécurité");
        titles.put(PREF_KEY_FORCE_INCOGNITO, "Forcer le mode navigation privée");
        titles.put(PREF_KEY_HIDE_INCOGNITO_ICON, "Masquer l'icône de navigation privée");
        titles.put(PREF_KEY_VOICE_INCOGNITO, "Dictée vocale en navigation privée");
        titles.put(PREF_KEY_CLIPBOARD_INCOGNITO, "Presse-papiers en navigation privée");
    }

    @Override
    public void populateSummaries(Map<String, String> summaries) {
        summaries.put(PREF_KEY_HEADER, "Personnalisation et réglages des patchs");
        summaries.put(PREF_KEY_ENABLE_IME, "Gboard est désactivé dans Android. Touchez pour l'activer dans Gérer les claviers.");
        summaries.put(PREF_KEY_SELECT_IME, "Gboard est activé mais pas en service. Touchez pour choisir Gboard comme clavier.");
        summaries.put(PREF_KEY_RESTART_GBOARD, "Touchez pour appliquer les modifications (nécessaire pour la plupart des options)");
        summaries.put(PREF_KEY_AMOLED, "Forcer un fond noir pur (#000000) sur les thèmes sombres");
        summaries.put(PREF_KEY_ZERO_BOTTOM_INSET, "Supprimer la marge sous le clavier en navigation par gestes");
        summaries.put(PREF_KEY_BOTTOM_PADDING, "Marge intérieure basse en pixels (0 pour un clavier affleurant, défaut : 0)");
        summaries.put(PREF_KEY_HIDE_IME_NAV_BAR, "Masquer la barre de navigation IME du système (sélecteur de clavier et boutons de réduction) sur Android 13+ pour un clavier affleurant. Désactivez pour conserver ces boutons");
        summaries.put(PREF_KEY_KEY_SHAPE_SELECTION, "Activer les styles de touches arrondies et sans bordure dans les thèmes");
        summaries.put(PREF_KEY_EMOJI_SCALE, "Ajuster la taille visuelle des émojis sur le clavier (50 % - 150 %)");
        summaries.put(PREF_KEY_ACCESS_POINTS_REDESIGN, "Activer la barre d'accès et le panneau repensés (panneau V2)");
        summaries.put(PREF_KEY_TOOLBAR_ITEM_COUNT, "Nombre maximal d'icônes affichées dans la barre supérieure (défaut : 5)");
        summaries.put(PREF_KEY_DISMISS_SUGGESTIONS, "Afficher un bouton de fermeture (X) dans la barre de suggestions");
        summaries.put(PREF_KEY_CURSOR_TRACKPAD, "Navigation du curseur 2D sur la barre d'espace");
        summaries.put(PREF_KEY_CLIPBOARD_EXTENDED_RETENTION, "Activer une durée de conservation personnalisée pour les éléments non épinglés");
        summaries.put(PREF_KEY_CLIPBOARD_RETENTION_HOURS, "Heures de conservation des éléments non épinglés avant suppression (défaut : 24 h)");
        summaries.put(PREF_KEY_CLIPBOARD_RAISE_LIMIT, "Activer une limite personnalisée pour les éléments non épinglés de l'historique");
        summaries.put(PREF_KEY_CLIPBOARD_UNPINNED_LIMIT, "Nombre maximal d'éléments non épinglés dans le presse-papiers (défaut : 50)");
        summaries.put(PREF_KEY_CLIPBOARD_GRID_LAYOUT, "Activer la disposition en plusieurs colonnes pour le presse-papiers");
        summaries.put(PREF_KEY_CLIPBOARD_GRID_COLUMNS, "Nombre de colonnes dans le presse-papiers (1, 2 ou 3. Défaut : 2)");
        summaries.put(PREF_KEY_CLIPBOARD_CHAR_LIMIT, "Maximum de caractères enregistrés par élément de texte, en milliers (défaut : 20 mille). Redémarrez Gboard pour appliquer");
        summaries.put(PREF_KEY_DECOUPLE_TOUCH_FEEDBACK, "Garder la vibration du clavier active même si le retour tactile du système Android est désactivé");
        summaries.put(PREF_KEY_MODERN_HAPTICS, "Utiliser les primitives haptiques d'Android (toucher net) au lieu d'un simple bourdonnement. Le curseur d'intensité mesure la force. Redémarrez Gboard pour appliquer");
        summaries.put(PREF_KEY_GRAMMAR_CHECKER, "Révision grammaticale intégrée et prédictions de rédaction intelligente");
        summaries.put(PREF_KEY_BLUETOOTH_MIC, "Activer l'entrée audio du micro Bluetooth pour la dictée vocale");
        summaries.put(PREF_KEY_FORCE_INCOGNITO, "Toujours fonctionner en navigation privée (désactive l'historique de saisie et l'apprentissage)");
        summaries.put(PREF_KEY_HIDE_INCOGNITO_ICON, "Masquer l'icône du masque de navigation privée dans la barre d'outils");
        summaries.put(PREF_KEY_VOICE_INCOGNITO, "Activer la dictée vocale dans les champs privés et en navigation privée");
        summaries.put(PREF_KEY_CLIPBOARD_INCOGNITO, "Activer l'historique du presse-papiers et le collage dans les champs privés et en navigation privée");
    }

    @Override
    public String getRestartToast() {
        return "Redémarrez Gboard pour appliquer les modifications";
    }

    @Override
    public String getRestartingToast() {
        return "Redémarrage de Gboard...";
    }

    @Override
    public String getRestartTitle(boolean pending) {
        if (pending) {
            return "Redémarrer Gboard (redémarrage en attente)";
        }
        return "Redémarrer le processus Gboard";
    }

    @Override
    public String getRestartSummary(boolean pending) {
        if (pending) {
            return "Modifications en attente ! Touchez ici pour redémarrer Gboard et les appliquer.";
        }
        return "Touchez pour appliquer les modifications (nécessaire pour la plupart des options)";
    }

    @Override
    public String formatUnit(String prefKey, int value) {
        switch (prefKey) {
            case PREF_KEY_BOTTOM_PADDING:
                return value + " px";
            case PREF_KEY_TOOLBAR_ITEM_COUNT:
                return value + (value == 1 ? " icône" : " icônes");
            case PREF_KEY_CLIPBOARD_RETENTION_HOURS:
                return value + " h";
            case PREF_KEY_CLIPBOARD_UNPINNED_LIMIT:
                return value + (value == 1 ? " élément" : " éléments");
            case PREF_KEY_CLIPBOARD_GRID_COLUMNS:
                return value + (value == 1 ? " colonne" : " colonnes");
            case PREF_KEY_CLIPBOARD_CHAR_LIMIT:
                return value + " mille caractères";
            case PREF_KEY_EMOJI_SCALE:
                return value + " %";
            default:
                return String.valueOf(value);
        }
    }
}
