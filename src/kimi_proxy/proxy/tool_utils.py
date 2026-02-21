"""
Utilitaires pour les tool calls dans le proxy.
Pourquoi: Générer et valider les IDs de tool calls selon les spécifications des providers.
"""
import re
import string
import secrets
import json
import time
from typing import Dict, Any, List, Optional, Tuple


# Configuration du circuit breaker pour la correction JSON
CIRCUIT_BREAKER_CONFIG = {
    "max_total_attempts": 10,
    "max_time_ms": 100,
    "enabled": True
}

# Métriques de correction JSON (pour analyse et monitoring)
JSON_FIX_METRICS = {
    "total_attempts": 0,
    "success_by_strategy": {
        "direct_fix": 0,
        "reconstruct_basic": 0,
        "reconstruct_complex": 0,
        "eval_fallback": 0,
        "all_failed": 0
    },
    "failure_reasons": []
}

def detect_and_merge_concatenated_json(json_str: str) -> str:
    """
    Détecte et fusionne les structures JSON concaténées/dupliquées.
    
    Exemple: '{"a": 1}{"b": 2}' -> '{"a": 1, "b": 2}'
    
    Args:
        json_str: Chaîne potentiellement contenant plusieurs JSON concaténés
        
    Returns:
        Chaîne JSON fusionnée ou originale si pas de concaténation détectée
    """
    if not json_str or len(json_str) < 4:
        return json_str
    
    # Cherche les patterns de concaténation: }{ ou }{
    # Un JSON valide se termine par } et le suivant commence par {
    concatenation_pattern = r'}\s*{'
    
    if not re.search(concatenation_pattern, json_str):
        return json_str
    
    try:
        # Extraction des objets JSON individuels
        # Pattern: trouve tous les objets JSON complets entre { et }
        objects = []
        depth = 0
        start_idx = None
        
        for i, char in enumerate(json_str):
            if char == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_str = json_str[start_idx:i+1]
                    try:
                        obj = json.loads(obj_str)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        # Ignore les fragments invalides
                        pass
                    start_idx = None
        
        if len(objects) > 1:
            # Fusionne tous les objets en un seul
            merged = {}
            for obj in objects:
                if isinstance(obj, dict):
                    merged.update(obj)
            
            if merged:
                return json.dumps(merged, ensure_ascii=False)
        
        return json_str
        
    except Exception as e:
        print(f"   Erreur détection concaténation: {e}")
        return json_str


def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Retourne le statut actuel du circuit breaker et les métriques.
    
    Returns:
        Dictionnaire avec statut et métriques
    """
    return {
        "config": CIRCUIT_BREAKER_CONFIG,
        "metrics": JSON_FIX_METRICS.copy()
    }


def reset_circuit_breaker_metrics():
    """Reset les métriques du circuit breaker."""
    global JSON_FIX_METRICS
    JSON_FIX_METRICS = {
        "total_attempts": 0,
        "success_by_strategy": {
            "direct_fix": 0,
            "reconstruct_basic": 0,
            "reconstruct_complex": 0,
            "eval_fallback": 0,
            "all_failed": 0
        },
        "failure_reasons": []
    }


def generate_tool_call_id(length: int = 9) -> str:
    """
    Génère un ID de tool call alphanumérique valide.
    
    Args:
        length: Longueur de l'ID (défaut: 9 pour NVIDIA)
        
    Returns:
        ID alphanumérique de la longueur spécifiée
        
    Raises:
        ValueError: Si length < 1
    """
    if length < 1:
        raise ValueError("Length must be at least 1")
    
    # Caractères autorisés: a-z, A-Z, 0-9
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def validate_tool_call_id(tool_id: str) -> bool:
    """
    Valide qu'un ID de tool call respecte le format requis.
    
    Args:
        tool_id: ID à valider
        
    Returns:
        True si valide, False sinon
    """
    # Format requis: a-z, A-Z, 0-9, longueur 9
    pattern = r'^[a-zA-Z0-9]{9}$'
    return bool(re.match(pattern, tool_id))


def fix_tool_calls_in_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Corrige les tool calls dans une requête en générant les IDs manquants.
    
    Args:
        body: Corps de la requête JSON
        
    Returns:
        Corps modifié avec les IDs de tool calls valides
    """
    if not isinstance(body, dict):
        return body
    
    # Traite les tool calls dans les messages
    messages = body.get('messages', [])
    for message in messages:
        if not isinstance(message, dict):
            continue
            
        # Vérifie les tool calls dans le message
        tool_calls = message.get('tool_calls', [])
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                    
                tool_call_id = tool_call.get('id')
                if not tool_call_id or not validate_tool_call_id(tool_call_id):
                    # Génère un nouvel ID valide
                    new_id = generate_tool_call_id()
                    tool_call['id'] = new_id
                    print(f"   [TOOL CALL] ID généré: {new_id}")
    
    return body


def reconstruct_complex_json(corrupted_str: str) -> str:
    """
    Reconstruction agressive pour JSON complexes très corrompus avec 15+ stratégies de correction.
    """
    try:
        # Méthode 1: Cherche les patterns de propriétés JSON valides
        # Extrait tous les patterns "clé": valeur
        import re

        # Pattern pour extraire les propriétés JSON
        property_pattern = r'"([^"]+)"\s*:\s*([^,}\]]*?)(?=,|"[^"]*"\s*:|})'

        properties = {}
        for match in re.finditer(property_pattern, corrupted_str):
            key = match.group(1)
            value_str = match.group(2).strip()

            # Essaie de parser la valeur
            try:
                # Pour les chaînes
                if value_str.startswith('"') and value_str.endswith('"'):
                    properties[key] = value_str[1:-1]
                # Pour les booléens
                elif value_str in ['true', 'false']:
                    properties[key] = value_str == 'true'
                # Pour les null
                elif value_str == 'null':
                    properties[key] = None
                # Pour les nombres
                elif value_str.replace('.', '').replace('-', '').isdigit():
                    properties[key] = float(value_str) if '.' in value_str else int(value_str)
                # Pour les arrays simples
                elif value_str.startswith('[') and value_str.endswith(']'):
                    # Essaie de parser comme array
                    try:
                        array_items = []
                        items = value_str[1:-1].split(',')
                        for item in items:
                            item = item.strip()
                            if item.startswith('"') and item.endswith('"'):
                                array_items.append(item[1:-1])
                            elif item in ['true', 'false']:
                                array_items.append(item == 'true')
                            elif item.replace('.', '').replace('-', '').isdigit():
                                array_items.append(float(item) if '.' in item else int(item))
                        properties[key] = array_items
                    except:
                        properties[key] = value_str  # Garde comme string
                else:
                    properties[key] = value_str
            except:
                properties[key] = value_str  # Garde comme string en cas d'erreur

        if properties:
            return json.dumps(properties, ensure_ascii=False)

        # Méthode 2: Reconstruction basée sur les tokens JSON
        # Cherche tous les tokens valides et les réassemble
        tokens = re.findall(r'"[^"]*"|true|false|null|\d+\.?\d*|\{|\}|\[|\]|,', corrupted_str)

        # Filtre et nettoie les tokens
        clean_tokens = []
        for token in tokens:
            token = token.strip()
            if token:
                clean_tokens.append(token)

        # Essaie de reconstruire une structure simple
        if len(clean_tokens) >= 3 and clean_tokens[0] == '{' and clean_tokens[-1] == '}':
            # C'est probablement un objet
            content_tokens = clean_tokens[1:-1]
            reconstructed = {}

            i = 0
            while i < len(content_tokens) - 1:
                if content_tokens[i].startswith('"') and content_tokens[i+1] == ':':
                    key = content_tokens[i][1:-1] if content_tokens[i].startswith('"') else content_tokens[i]
                    value_token = content_tokens[i+2] if i+2 < len(content_tokens) else 'null'

                    # Parse la valeur
                    if value_token.startswith('"'):
                        reconstructed[key] = value_token[1:-1]
                    elif value_token in ['true', 'false']:
                        reconstructed[key] = value_token == 'true'
                    elif value_token == 'null':
                        reconstructed[key] = None
                    elif value_token.replace('.', '').replace('-', '').isdigit():
                        reconstructed[key] = float(value_token) if '.' in value_token else int(value_token)
                    else:
                        reconstructed[key] = value_token

                    i += 3  # Saute la clé, le :, et la valeur
                    if i < len(content_tokens) and content_tokens[i] == ',':
                        i += 1  # Saute la virgule
                else:
                    i += 1

            if reconstructed:
                return json.dumps(reconstructed, ensure_ascii=False)

        return None

    except Exception as e:
        print(f"   Complex reconstruction error: {e}")
        return None


def fix_malformed_json_arguments(arguments_str: str, enable_circuit_breaker: bool = True) -> str:
    """
    Essaie de corriger des arguments JSON malformés avec circuit breaker et métriques.

    Args:
        arguments_str: String JSON potentiellement malformé
        enable_circuit_breaker: Active le circuit breaker pour limiter les tentatives

    Returns:
        String JSON corrigé ou original si correction impossible
    """
    global JSON_FIX_METRICS
    
    if not arguments_str or not arguments_str.strip():
        return arguments_str

    # Circuit breaker: vérifie le nombre total de tentatives
    if enable_circuit_breaker and CIRCUIT_BREAKER_CONFIG["enabled"]:
        if JSON_FIX_METRICS["total_attempts"] >= CIRCUIT_BREAKER_CONFIG["max_total_attempts"]:
            print(f"   ⚠️ Circuit breaker activé: max attempts reached ({CIRCUIT_BREAKER_CONFIG['max_total_attempts']})")
            JSON_FIX_METRICS["failure_reasons"].append("circuit_breaker_max_attempts")
            return arguments_str
    
    start_time = time.time()
    JSON_FIX_METRICS["total_attempts"] += 1
    attempt_count = 0

    # Essaie de corriger les problèmes courants
    fixed = arguments_str.strip()
    original = fixed
    print(f"   Original: {fixed[:150]}...")

    # ÉTAPE 1: Détection et fusion des JSON concaténés
    fixed = detect_and_merge_concatenated_json(fixed)
    if fixed != original:
        print(f"   After concatenation merge: {fixed[:150]}...")
        try:
            json.loads(fixed)
            print(f"   ✅ JSON valide après fusion concaténation")
            return fixed
        except json.JSONDecodeError:
            pass  # Continue avec autres corrections

    # ÉTAPE 2: Correction directe pour le pattern corrompu observé
    attempt_count += 1
    for _ in range(5):  # Limite à 5 itérations pour éviter les boucles infinies
        old_fixed = fixed
        fixed = fixed.replace('"rules": [""]cursor{"', '"rules": ["cursor"], "')
        if fixed == old_fixed:
            break
    print(f"   After direct pattern fix (looped): {fixed[:150]}...")

    # ÉTAPE 3: Correction générale pour les patterns similaires
    attempt_count += 1
    fixed = re.sub(r'\[""\](\w+)\{', r'["\1"], {', fixed)
    print(f"   After general array fix: {fixed[:150]}...")

    # ÉTAPE 4: Supprime les trailing commas
    attempt_count += 1
    fixed = fixed.replace(',}', '}').replace(',]', ']')
    print(f"   After trailing comma fix: {fixed[:150]}...")

    # ÉTAPE 5: Corrige les virgules manquantes entre propriétés
    attempt_count += 1
    fixed = re.sub(r'(\w+)"\s*"(\w+)":', r'\1","\2":', fixed)
    print(f"   After property comma fix: {fixed[:150]}...")

    # ÉTAPE 6: Pattern pour valeurs numériques sans virgule
    attempt_count += 1
    fixed = re.sub(r'(\d+)\s*"(\w+)":', r'\1, "\2":', fixed)
    print(f"   After numeric comma fix: {fixed[:150]}...")

    # ÉTAPE 7: Pattern pour true/false/null sans virgule
    attempt_count += 1
    fixed = re.sub(r'(true|false|null)\s*"(\w+)":', r'\1, "\2":', fixed)
    print(f"   After boolean comma fix: {fixed[:150]}...")

    # ÉTAPE 8: Reconstruction spécifique pour le pattern observé
    attempt_count += 1
    fixed = re.sub(r'\[""\]([a-zA-Z_]\w*)\{([a-zA-Z_]\w*)', r'["\1"], "\2": {', fixed)
    print(f"   After specific reconstruction: {fixed[:150]}...")

    # ÉTAPE 9: Pattern pour les arrays vides suivis de propriétés fusionnées
    attempt_count += 1
    fixed = re.sub(r'\[\](\w+)\{', r'[], "\1": {', fixed)
    print(f"   After empty array fix: {fixed[:150]}...")

    # ÉTAPE 10: Pattern pour corriger les arrays avec éléments vides
    attempt_count += 1
    fixed = re.sub(r'\[""\]([^,])', r'["\1"]', fixed)
    print(f"   After empty element fix: {fixed[:150]}...")

    # ÉTAPE 11: Corrections avancées pour JSON complexes
    attempt_count += 1
    
    # Pattern pour gérer les longues chaînes avec guillemets non échappés
    fixed = re.sub(r'("(?:[^"\\]|\\.)*")', lambda m: m.group(1).replace("'", "\\'"), fixed)
    
    # Pattern pour corriger les virgules manquantes dans les objets imbriqués
    fixed = re.sub(r'("\w+")\s*(")', r'\1,\2', fixed)
    
    # Correction pour les virgules manquantes avant les propriétés d'objet
    fixed = re.sub(r'(\w+|\]|\})\s*\{', r'\1, {', fixed)
    fixed = re.sub(r'(\w+|\]|\})\s*\[', r'\1, [', fixed)
    
    # Correction pour les virgules manquantes après les valeurs
    fixed = re.sub(r'(true|false|null|\d+|\w+)\s*(")', r'\1,\2', fixed)

    # ÉTAPE 13: Correction spécifique pour concaténation avec duplication
    # Pattern: {"a": "val" "b": 1{"a": "val", "b": 1} -> {"a": "val", "b": 1}
    # Détecte la répétition d'un objet JSON dans la chaîne
    if len(fixed) > 50:
        try:
            # Cherche des patterns de duplication: mot-clé répété avec accolade
            dup_pattern = r'(\{"[^"]+"\s*:\s*"[^"]*"[^}]*\})\s*\{'
            match = re.search(dup_pattern, fixed)
            if match:
                potential_dup = match.group(1)
                # Vérifie si le reste contient une version similaire
                rest = fixed[match.end()-1:]
                if potential_dup[:30] in rest[:60]:
                    # Garde seulement la première occurrence
                    fixed = potential_dup
                    print(f"   Applied duplicate object fix")
        except Exception as e:
            pass

    # ÉTAPE 14: Correction pour virgule manquante avant propriété
    # Pattern: "value" "next": -> "value", "next":
    # Détecte quand une valeur string est suivie directement d'une clé
    fixed = re.sub(r'("[^"]*")\s*"(\w+)":', r'\1, "\2":', fixed)
    print(f"   After comma before property fix: {fixed[:150]}...")

    # ÉTAPE 15: Correction pour virgule manquante après valeur dans objet
    # Pattern: ..."key": "value"{...} -> ..."key": "value", {...}
    fixed = re.sub(r'("[^"]*"|\d+|true|false|null)\s*\{', r'\1, {', fixed)
    print(f"   After comma before brace fix: {fixed[:150]}...")

    print(f"   After advanced corrections: {fixed[:150]}...")

    # ÉTAPE 12: Correction position-based pour longs JSON
    if len(fixed) > 1000:
        attempt_count += 1
        print(f"   Long JSON detected ({len(fixed)} chars), applying length-based fixes...")
        
        # Généralisation: cherche les positions problématiques potentielles
        # au lieu de hardcoder 1146
        potential_error_positions = [1146, len(fixed) // 2, len(fixed) - 100]
        
        for error_pos in potential_error_positions:
            if len(fixed) > error_pos:
                start_pos = max(0, error_pos - 50)
                end_pos = min(len(fixed), error_pos + 50)
                context = fixed[start_pos:end_pos]
                
                # Cherche des patterns de virgule manquante dans ce contexte
                context_fixed = re.sub(r'"\s+"(\w+)":', r'", "\1":', context)
                if context_fixed != context:
                    before_context = fixed[:start_pos]
                    after_context = fixed[end_pos:]
                    fixed = before_context + context_fixed + after_context
                    print(f"   Applied context-specific comma fix at position {error_pos}")
                    break  # Applique une seule correction

    print(f"   After position-based fixes: {fixed[:150]}...")

    # Vérifie le temps écoulé pour le circuit breaker
    elapsed_ms = (time.time() - start_time) * 1000
    if enable_circuit_breaker and elapsed_ms > CIRCUIT_BREAKER_CONFIG["max_time_ms"]:
        print(f"   ⚠️ Circuit breaker: timeout ({elapsed_ms:.1f}ms > {CIRCUIT_BREAKER_CONFIG['max_time_ms']}ms)")
        JSON_FIX_METRICS["failure_reasons"].append("circuit_breaker_timeout")
        return arguments_str

    # Essaie de parser pour valider
    try:
        json.loads(fixed)
        print(f"   ✅ JSON valide après correction directe")
        JSON_FIX_METRICS["success_by_strategy"]["direct_fix"] += 1
        return fixed
    except json.JSONDecodeError as e:
        print(f"   Tentative correction directe échouée: {e}")

    # Si toujours invalide, essaie une approche plus agressive
    try:
        # ATTENTION: ceci est dangereux mais peut corriger certains cas
        fixed_dict = eval(fixed.replace('true', 'True').replace('false', 'False').replace('null', 'None'))
        if isinstance(fixed_dict, dict):
            result = json.dumps(fixed_dict)
            print(f"   ✅ JSON valide après eval fallback")
            JSON_FIX_METRICS["success_by_strategy"]["eval_fallback"] += 1
            return result
    except Exception as eval_error:
        print(f"   Eval approach failed: {eval_error}")

    # Dernière tentative: reconstruction complète depuis les paramètres détectés
    try:
        print(f"   Tentative reconstruction complète...")
        reconstructed = reconstruct_from_corrupted_arguments(fixed)
        if reconstructed and reconstructed != fixed:
            json.loads(reconstructed)  # Valide
            print(f"   ✅ Reconstruction basique réussie")
            JSON_FIX_METRICS["success_by_strategy"]["reconstruct_basic"] += 1
            return reconstructed
        else:
            print(f"   Reconstruction basique échouée")
    except Exception as reconstruct_error:
        print(f"   Reconstruction basique failed: {reconstruct_error}")

    # DERNIÈRE TENTATIVE: Reconstruction agressive pour JSON complexes
    try:
        print(f"   Tentative reconstruction agressive...")
        aggressive_result = reconstruct_complex_json(fixed)
        if aggressive_result:
            json.loads(aggressive_result)  # Valide
            print(f"   ✅ Reconstruction complexe réussie")
            JSON_FIX_METRICS["success_by_strategy"]["reconstruct_complex"] += 1
            return aggressive_result
    except Exception as aggressive_error:
        print(f"   Reconstruction complexe failed: {aggressive_error}")

    # Si toujours invalide, retourne l'original
    print(f"   ❌ Toutes les corrections ont échoué après {attempt_count} tentatives ({elapsed_ms:.1f}ms)")
    JSON_FIX_METRICS["success_by_strategy"]["all_failed"] += 1
    JSON_FIX_METRICS["failure_reasons"].append(f"all_strategies_failed_after_{attempt_count}_attempts")
    return arguments_str
