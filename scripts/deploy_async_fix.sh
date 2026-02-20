#!/bin/bash
# Script de déploiement du correctif async/await pour auto-memory
# Vérifie que le correctif est appliqué et redémarre les services si nécessaire

set -e

echo "🔧 Déploiement du correctif RuntimeWarning 'coroutine not awaited'..."
echo "=================================================================="

# Vérifie que le fichier existe
AUTO_MEMORY_FILE="src/kimi_proxy/features/mcp/auto_memory.py"

if [ ! -f "$AUTO_MEMORY_FILE" ]; then
    echo "❌ Erreur: Fichier $AUTO_MEMORY_FILE introuvable"
    exit 1
fi

echo "✅ Fichier auto_memory.py trouvé"

# Vérifie que le correctif est appliqué (await présent)
if grep -q "entry = await manager.store_memory(" "$AUTO_MEMORY_FILE"; then
    echo "✅ Correctif async/await déjà appliqué"
else
    echo "❌ ERREUR: Le correctif n'est pas appliqué!"
    echo "   La ligne 'entry = await manager.store_memory(' est manquante"
    exit 1
fi

# Vérifie qu'il n'y a pas d'appels non-awaités
echo "🔍 Recherche d'appels store_memory non-awaités..."
NON_AWAITED=$(grep -n "manager.store_memory(" "$AUTO_MEMORY_FILE" | grep -v "await" | wc -l)

if [ "$NON_AWAITED" -eq 0 ]; then
    echo "✅ Aucun appel store_memory non-awaité détecté"
else
    echo "❌ ERREUR: $NON_AWAITED appel(s) store_memory non-awaité(s) détecté(s):"
    grep -n "manager.store_memory(" "$AUTO_MEMORY_FILE" | grep -v "await"
    exit 1
fi

# Test rapide avec Python
echo "🧪 Test de validation du correctif..."
if python3 test_async_fix.py > /dev/null 2>&1; then
    echo "✅ Test de validation réussi"
else
    echo "❌ ERREUR: Test de validation échoué"
    python3 test_async_fix.py
    exit 1
fi

# Monitoring des warnings
echo "🔍 Monitoring des RuntimeWarning..."
if python3 scripts/monitor_async_warnings.py > /dev/null 2>&1; then
    echo "✅ Aucun RuntimeWarning détecté"
else
    echo "❌ ERREUR: RuntimeWarning toujours présent"
    python3 scripts/monitor_async_warnings.py
    exit 1
fi

# Vérifie si le service tourne et propose de le redémarrer
if pgrep -f "kimi-proxy" > /dev/null; then
    echo "🔄 Service Kimi Proxy détecté en cours d'exécution"
    echo "   Souhaitez-vous redémarrer le service pour appliquer le correctif? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "🔄 Redémarrage du service..."
        ./bin/kimi-proxy-stop
        sleep 2
        ./bin/kimi-proxy-start
        echo "✅ Service redémarré"
    else
        echo "ℹ️  Service non redémarré (le correctif sera actif au prochain redémarrage)"
    fi
else
    echo "ℹ️  Service Kimi Proxy non détecté en cours d'exécution"
fi

echo ""
echo "🎉 DÉPLOIEMENT TERMINÉ AVEC SUCCÈS!"
echo "   ✅ Correctif async/await appliqué"
echo "   ✅ Tests de validation passés"
echo "   ✅ Aucun RuntimeWarning détecté"
echo "   🚀 L'auto-memory est maintenant opérationnel sans warnings"