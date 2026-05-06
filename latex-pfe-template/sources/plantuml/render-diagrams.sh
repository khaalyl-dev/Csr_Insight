#!/usr/bin/env bash
# Génère les PNG des chapitres 4–6 à partir des sources .puml (nécessite Java).
# Télécharger le JAR : https://github.com/plantuml/plantuml/releases → plantuml-*.*.*.jar
# Puis : mkdir -p ../../tools && cp plantuml-*.jar ../../tools/plantuml.jar
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/sources/plantuml"
JAR="$ROOT/tools/plantuml.jar"
if [[ ! -f "$JAR" ]]; then
  echo "Fichier manquant : $JAR" >&2
  echo "Téléchargez plantuml depuis GitHub releases et enregistrez-le sous ce nom." >&2
  exit 1
fi
JAVA=(java -Djava.awt.headless=true -jar "$JAR" -charset UTF-8 -tpng)
mkdir -p "$ROOT/figures/chapitre-04" "$ROOT/figures/chapitre-05" "$ROOT/figures/chapitre-06"
"${JAVA[@]}" -o "$ROOT/figures/chapitre-04" \
  "$SRC/diagramme-cas-utilisation-plans-activites.puml" \
  "$SRC/diagramme-classe-plans-activites.puml"
"${JAVA[@]}" -o "$ROOT/figures/chapitre-05" \
  "$SRC/diagramme-cas-utilisation-workflow-transverse.puml" \
  "$SRC/diagramme-classe-workflow-transverse.puml"
"${JAVA[@]}" -o "$ROOT/figures/chapitre-06" \
  "$SRC/diagramme-cas-utilisation-bi-kpi.puml" \
  "$SRC/diagramme-classe-bi-kpi.puml"
echo "OK — PNG mis à jour dans figures/chapitre-04|05|06"
