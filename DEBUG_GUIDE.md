# 🔍 Guide de Débogage WhatsApp AI V5

Ce guide vous explique comment utiliser le système de débogage complet mis en place pour votre application WhatsApp AI.

## 🚀 Démarrage Rapide

### 1. Diagnostic du Système
Avant de démarrer l'application, lancez le diagnostic complet :

```bash
python diagnostic.py
```

Ce script vérifie :
- ✅ Variables d'environnement
- ✅ Connexion à MongoDB
- ✅ Composants IA
- ✅ Utilitaires WhatsApp
- ✅ Application Flask

### 2. Démarrage avec Débogage Complet
```bash
python run.py
```

Le système génère automatiquement :
- 📺 Logs en temps réel dans le terminal
- 📁 Fichier de log détaillé : `debug_log_YYYYMMDD_HHMMSS.log`

## 📊 Compréhension des Logs

### 🔵 Séparations par Fonction
Chaque étape du traitement est clairement séparée avec des titres comme :

```
================================================================================
🔵 DÉBUT DU TRAITEMENT DU WEBHOOK
================================================================================
```

### 🎯 Types de Messages

| Emoji | Type | Description |
|-------|------|-------------|
| 🔵 | INFO | Informations normales |
| 🟡 | WARNING | Avertissements |
| 🔴 | ERROR | Erreurs |
| ✅ | SUCCESS | Succès |
| ❌ | FAILURE | Échec |
| 🔍 | ANALYSIS | Analyse |
| 🚀 | ACTION | Action en cours |
| 📋 | DATA | Données |
| 👤 | USER | Information utilisateur |
| 🤖 | AI | Intelligence artificielle |
| 🔧 | TOOL | Outils |
| 📤 | SEND | Envoi |
| 📥 | RECEIVE | Réception |

## 🔄 Flux de Traitement Détaillé

### 1. Réception du Webhook
```
🔵 DÉBUT DU TRAITEMENT DU WEBHOOK
🔄 Étape 1: Récupération du body de la requête
✅ Body récupéré avec succès
📋 Contenu du body: {...}
```

### 2. Extraction des Données
```
🔵 ÉTAPE 2: EXTRACTION DES DONNÉES
🔍 Extraction de l'entry...
📥 Entry extraite: {...}
🔍 Extraction des changes...
📥 Changes extraites: {...}
```

### 3. Validation du Message
```
🔵 ÉTAPE 4: VALIDATION DU MESSAGE
🔍 Vérification de la validité du message...
✅ Message WhatsApp valide détecté
```

### 4. Traitement Asynchrone
```
🔵 LANCEMENT DU TRAITEMENT ASYNCHRONE
🚀 Lancement du thread de traitement asynchrone...
✅ Thread lancé avec succès
```

### 5. Génération de Réponse IA
```
🔵 DÉBUT DE LA GÉNÉRATION DE RÉPONSE IA
🔵 ÉTAPE 1: DÉTECTION DE LA LANGUE
🌍 Langue détectée: fr
🔵 ÉTAPE 2: SAUVEGARDE DU MESSAGE UTILISATEUR
💾 Sauvegarde du message utilisateur en base de données...
```

### 6. Envoi de Message
```
🔵 ENVOI DU MESSAGE WHATSAPP
🌐 URL de l'API: https://graph.facebook.com/...
📤 Données à envoyer: {...}
✅ Message envoyé avec succès !
```

## 🛠️ Débogage des Problèmes Courants

### ❌ Problème de Contexte Flask
```
🔴 ERREUR DANS LE TRAITEMENT ASYNCHRONE
❌ Erreur lors du traitement asynchrone: Working outside of application context
```
**Solution :** Le contexte Flask est maintenant géré automatiquement avec `app.app_context()`

### ❌ Problème de Doublons
```
🟡 DOUBLON DÉTECTÉ
⚠️ Message doublon détecté pour 212643370003: salut
```
**Solution :** Le système ignore automatiquement les doublons pendant 20 secondes

### ❌ Problème de Connexion API
```
🔴 ERREUR: REQUÊTE HTTP
❌ Échec de la requête: HTTPError
```
**Solution :** Vérifiez vos tokens et la configuration réseau

## 📁 Structure des Logs

### Logs en Temps Réel (Terminal)
- Affichage immédiat avec couleurs et emojis
- Séparations visuelles claires
- Informations essentielles

### Logs Détaillés (Fichier)
- Tous les détails techniques
- Traceback complets des erreurs
- Métadonnées complètes
- Horodatage précis

## 🔧 Configuration du Débogage

### Niveaux de Logging
```python
# Dans run.py
logging.getLogger().setLevel(logging.INFO)  # INFO, DEBUG, WARNING, ERROR
```

### Filtrage des Logs
Pour voir seulement les erreurs :
```bash
python run.py 2>&1 | grep "🔴\|❌"
```

Pour voir seulement les succès :
```bash
python run.py 2>&1 | grep "✅\|🔵"
```

## 🎯 Cas d'Usage Spécifiques

### 1. Déboguer un Message Qui N'arrive Pas
Cherchez dans les logs :
```
🔵 VALIDATION DU MESSAGE WHATSAPP
📋 Présence de 'object': True -> whatsapp_business_account
📋 Présence de 'entry': True
```

### 2. Déboguer une Réponse IA Incorrecte
Cherchez :
```
🔵 ÉTAPE 6: TRAITEMENT DES APPELS D'OUTILS
🤖 Réponse brute de l'IA: ...
🧹 Réponse nettoyée: ...
```

### 3. Déboguer l'Envoi de Message
Cherchez :
```
🔵 ENVOI DU MESSAGE WHATSAPP
📊 Statut de réponse: 200
✅ Message envoyé avec succès !
```

## 🚨 Alertes Importantes

### Messages à Surveiller
- `🔴 ERREUR` : Erreurs critiques nécessitant une intervention
- `🟡 WARNING` : Avertissements à surveiller
- `⚠️ TIMEOUT` : Problèmes de performance
- `❌ ÉCHEC` : Opérations qui ont échoué

### Actions Recommandées
1. **Erreurs récurrentes** : Analyser les logs détaillés
2. **Timeouts fréquents** : Vérifier la configuration réseau
3. **Doublons excessifs** : Vérifier la configuration webhook
4. **Erreurs IA** : Vérifier les tokens et quotas API

## 📊 Monitoring en Production

### Surveillance des Logs
```bash
# Suivre les logs en temps réel
tail -f debug_log_*.log

# Compter les erreurs
grep -c "🔴\|❌" debug_log_*.log

# Analyser les performances
grep "⏰\|🕐" debug_log_*.log
```

### Nettoyage des Logs
```bash
# Supprimer les logs de plus de 7 jours
find . -name "debug_log_*.log" -mtime +7 -delete
```

Ce système de débogage vous permet de suivre précisément chaque étape du traitement de vos messages WhatsApp et d'identifier rapidement les problèmes potentiels. 🎉 