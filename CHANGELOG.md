# Changelog

## 0.6.1
- Instalador: etapas de testes e de atualização do PyInstaller viram aviso e a compilação continua; `--strict-tests` para exigir os testes.
- Variável de ambiente `REST_NO_EDITOR` para não abrir editores externos (usada nos testes).
- Marcadores ✓ / ✗ mais estreitos no instalador.

## 0.6.0
- `installer.py` com banner REST e barra de progresso em gradiente (laranja → rosa → roxo) e log em `build.log`.
- `build_exe.bat` e `build_exe.sh` chamam o instalador (`--skip-tests`, `--dry-run`, `--no-color`).
- `.gitattributes` (`.bat` com CRLF, `.sh` com LF).

## 0.5.0
- Interface responsiva: 4 faixas de largura, altura dos painéis adaptável e modo compacto para janelas pequenas.
- Saída do terminal com quebra de linha e rolagem por página; cabeçalho e rodapé adaptáveis à largura.
- README reorganizado.

## 0.4.0
- 11 temas: `crimson`, `blush`, `rosewhip`, `ruby`, `midnight`, `gold`, `lavender`, `tangerine`, `forest`, `ocean` e `cyberpunk`.
- Fonte do exportador de PNG ampliada (`( ) / \ | ^ v &` e outros símbolos).

## 0.3.0
- Artes `fire` e `tunnel`; temas `ember`, `aurora`, `synthwave` e `sakura`.
- Protetor de tela com relógio (`clock on|off`) e playlist de artes (`playlist`, `cycle`).
- Comando `doctor` (e `rest doctor`): tamanho real da janela, cores 24 bits, tela cheia e pastas.
- Painel de parâmetros mostra `clock` e `playlist`.

## 0.2.0
- Tamanho do terminal lido da janela real, acompanhando a tela cheia.
- Disco do buraco negro até as bordas (`fill`); fundo de estrelas e nebulosa no buraco negro, na galáxia e no donut.
- Descansos próprios: `new`, `import`, `rm`, recarga ao vivo, artes `.txt` (animação por `---frame---`) e plugins `.py`.
- `S` entra em tela cheia de verdade (Alt+Enter no Windows, `wmctrl` no X11) e desfaz ao sair.
- README com galeria ASCII, tutoriais e solução de problemas.

## 0.1.0
- Primeira versão: buraco negro ASCII, 7 artes, interface em painéis, terminal `>_`, wallpaper e lockscreen em PNG.
