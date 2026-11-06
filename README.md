# ConectaTudo 1.1 — Android + Windows (independente)

Um único **ZIP com dois projetos** para o GitHub Actions gerar um **APK Android** e um **EXE portátil Windows**. Usa a **mesma rede Wi-Fi ou hotspot**, sem precisar de conexão com a internet. O Legion Go não precisa de câmera; pode conectar por IP e PIN.

## O que mudou em relação à 1.0

1. **📷 QR dentro do Android**: o botão **Ler QR** abre uma tela de leitura dentro do próprio APK, pede autorização da câmera **antes** de iniciá-la e retorna para preencher IP e PIN. Não utiliza mais `IntentIntegrator` com uma tela externa. Isso elimina uma possível origem do fechamento relatado na 1.0, mas o funcionamento precisa ser verificado no aparelho real. Se não houver câmera ou autorização, use IP/PIN.
2. **💬 Mensagens automáticas**: o Android atualiza as mensagens/arquivos recebidos aproximadamente a cada 1,3 segundo; o Windows exibe novas mensagens automaticamente em sua janela, sem botão Atualizar. O painel no navegador também faz atualização automática.
3. **📤 Progresso de envio**: Android e Windows mostram percentual, bytes enviados/tamanho total, velocidade aproximada e previsão de tempo. No navegador, a transferência utiliza `XMLHttpRequest` para mostrar o andamento do upload; **Cancelamento** interrompe o envio do navegador.
4. **📥 Progresso de recebimento**: a interface Android e Windows mostram o arquivo sendo recebido e bytes transferidos; o painel acompanha a rota `/api/transfers`. A rota de acompanhamento é nova; aplicativos antigos 1.0 continuam aceitando envios, mas não mostram todos esses detalhes.
5. **🖥️ Tela menos travada**: o Android agora tenta gerar imagens JPEG até aproximadamente 1440 pixels no maior eixo, qualidade 76, a cada ~260 ms. O Windows usa até 1600×1000 pixels, qualidade 76; o navegador pede novas imagens após finalizar a anterior, sem sobrepor downloads. A taxa real depende de desempenho e rede. **Ainda é compartilhamento por imagens JPEG, não vídeo fluido de baixa latência**.
6. **📱 APK separado**: `applicationId 'br.app.conectatudo.v11'`, rótulo **ConectaTudo 1.1**, `versionCode 11`. Pode ficar instalado junto ao ConectaTudo 1.0 (`br.app.conectatudo.v1`).
7. **💻 Windows separado**: executável `ConectaTudo-Windows-1.1.exe`; instalador opcional `ConectaTudo-Setup-1.1.exe` com `AppId` próprio e diretório próprio para coexistir com o instalador anterior.

## Como gerar pelo Gerenciador GitHub

1. Baixe o ZIP completo e envie ao **repositório novo** pelo Gerenciador GitHub no celular. Os diretórios `android/`, `windows/` e `.github/` devem ficar na **raiz** do repositório (sem uma pasta extra).
2. O GitHub Actions inicia dois workflows de compilação: **Compilar Android APK** e **Compilar Windows EXE**.
3. Artefato **`ConectaTudo-Android-1.1-INDEPENDENTE-APK`**: contém `app-debug.apk`. Instale no celular ou tablet.
4. Artefato **`ConectaTudo-Windows-1.1-EXE`**: contém `ConectaTudo-Windows-1.1.exe` portátil para o Legion Go. Não precisa de Python no Windows.
5. Opcional: artefato `ConectaTudo-Windows-1.1-INSTALADOR`, se o GitHub conseguir instalar Inno Setup, contém `ConectaTudo-Setup-1.1.exe`.
6. **Não mantenha ConectaTudo 1.0 e 1.1 com seus servidores abertos simultaneamente no mesmo aparelho.** Ambos usam porta TCP **8765** e descoberta UDP **39402**; feche um antes de iniciar o outro. O fato de serem apps separados não libera a mesma porta para dois serviços.

## Conectar pelo hotspot sem internet

1. Crie um hotspot no POCO (ou conecte os dispositivos ao mesmo Wi-Fi local).
2. Conecte o Legion Go a essa rede.
3. Abra ConectaTudo 1.1 nos dois dispositivos. Permita a porta 8765 no **firewall de rede privada** do Windows se solicitado.
4. Use **Procurar dispositivos**; se não aparecer, digite o endereço IP e o PIN do outro aparelho.
5. Para celular/tablet, no receptor pressione **Mostrar QR** e no outro **Ler QR**. Agora ele abre o visor da câmera no próprio aplicativo. Se a câmera falhar, utilize IP/PIN.
6. Envie arquivos e textos, ou peça ao outro aparelho para iniciar o compartilhamento da tela.

## Permissões

- Câmera no Android: solicitada **somente quando o usuário toca em Ler QR**; pode ser recusada e usar IP/PIN.
- Compartilhamento de tela Android: exige **MediaProjection** com confirmação do Android para cada sessão. Em versões recentes o sistema pode mostrar informações adicionais da captura.
- Serviço em primeiro plano Android: indicado por notificação.
- Windows: acesso à rede privada no firewall (somente se estiver em rede confiável).
- **Não exige Shizuku, root nem liberar configurações restritas.**

## O que ainda não existe (planejado)

- **Internet entre redes diferentes**: esta versão não inclui servidor de sinalização, VPN, NAT traversal/TURN, nem retransmissão. **Não abra a porta 8765 na internet.**
- **Controle remoto** de mouse/toque/teclado: ainda não implementado. O botão **Ver tela** só exibe a imagem, não controla o outro aparelho.
- **Vídeo com áudio em baixa latência e 30/60 fps**: captura atual utiliza JPEG periódico; foram feitos ajustes para reduzir atraso, mas não é um sistema de vídeo em tempo real.
- **Criptografia dos arquivos em trânsito**: o aplicativo ainda utiliza HTTP + PIN de seis dígitos. Só utilize em hotspot/rede privada confiável. Não envie dados confidenciais em redes desconhecidas.
- Pausar/retomar arquivos grandes após perder a conexão e transferência de diretórios inteiros mantendo a estrutura também não estão implementados.

## Testes

- O código Python pode ser verificado com `python -m compileall -q windows` e o servidor pode ser testado localmente.
- **A compilação do Android e do Windows deve ser confirmada nos próprios GitHub Actions.** Os dispositivos e a câmera precisam de testes reais antes que se possa afirmar que o travamento foi resolvido.
- Android: Java 17, AGP 8.7.3, Gradle 8.9, compileSdk/targetSdk 35.
- Windows: Python 3.12, PyInstaller, Pillow, psutil.

## Estrutura (raiz do ZIP)

```
.github/workflows/android.yml
.github/workflows/windows.yml
android/build.gradle
android/settings.gradle
android/gradle.properties
android/app/build.gradle
android/app/src/main/AndroidManifest.xml
android/app/src/main/java/br/app/conectatudo/v1/*.java
android/app/src/main/assets/painel.html
android/app/src/main/res/values/styles.xml
windows/app.py
windows/host.py
windows/painel.html
windows/requirements.txt
windows/ConectaTudo.iss
README.md
```
