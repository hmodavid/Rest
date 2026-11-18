#!/usr/bin/env sh
# Instalador do Rest (Linux): abre o installer.py com banner e barra de progresso.
# Requer Python 3.9+. Opcoes: --skip-tests, --dry-run, --no-color
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    exec "$py" installer.py "$@"
  fi
done
echo "Python 3.9+ nao encontrado. Instale pelo gerenciador de pacotes (ex.: sudo apt install python3 python3-pip)." >&2
exit 1
