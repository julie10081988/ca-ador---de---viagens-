# Caçador de Viagens — instalação

Projeto independente do ChatGPT: painel GitHub Pages, monitoramento GitHub Actions e notificações Telegram.

## 1. Publicar
1. Crie uma conta no https://github.com e um repositório **privado** (ou público se aceitar que o código e os resultados fiquem visíveis). Envie todos os arquivos desta pasta, inclusive `.github/workflows/monitor.yml`.
2. Em **Settings → Pages**, escolha **Deploy from a branch**, `main`, `/ (root)` e salve. **Atenção:** a disponibilidade do GitHub Pages para repositórios privados depende do plano; no plano gratuito, normalmente é necessário repositório público para publicar pelo Pages. Não coloque segredos nos arquivos públicos.
3. O painel ficará em `https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/` após publicação.

## 2. Telegram
1. No Telegram, converse com **@BotFather**, envie `/newbot` e siga as instruções. Ele fornecerá um token **secreto**.
2. Envie `/start` para seu novo bot.
3. Para descobrir o chat ID, abra `https://api.telegram.org/botSEU_TOKEN/getUpdates` **somente no seu navegador privado**, após enviar uma mensagem ao bot. Copie o número `message.chat.id`. Não compartilhe token ou URL com ninguém.
4. Em GitHub → repositório → **Settings → Secrets and variables → Actions**, crie os secrets `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
5. Execute **Actions → Monitorar passagens → Run workflow** para testar o monitor. Sem fonte de dados não haverá mensagem de oferta; para testar o Telegram, execute localmente uma mensagem de teste com a API do Telegram, sem expor o token.

## 3. Fonte de preços (ainda precisa contratar/configurar)
Adicione o secret `FLIGHTS_FEED_URL` com um endpoint HTTPS autorizado que retorne uma lista JSON de ofertas atuais. Se necessário, `FLIGHTS_FEED_KEY` é enviado como bearer token. **Este projeto não inclui uma fonte de passagens, não faz scraping de companhias e não promete disponibilidade Azul.**

Formato de cada item:
```json
{"origin":"REC","destination":"LIS","international":true,"departure":"2027-02-10","return":"2027-02-20","type":"cash","currency":"BRL","price_brl":2850,"airline":"Exemplo","url":"https://exemplo.com/oferta"}
```
Para pontos Azul, use `"type":"azul","points":90000,"taxes_brl":320` no lugar dos campos de preço. Os valores acima são **apenas exemplos de estrutura, não ofertas reais**.

O monitor valida origem REC, internacional, viagem de 9 a 11 dias, ida e volta nos próximos seis meses e teto de R$ 4.000 para dinheiro. Para Azul, qualquer quantidade de pontos positiva é aceita. A fonte precisa devolver ofertas reais e atualizadas; o sistema não verifica diretamente o inventário da companhia. O monitor envia uma vez por combinação de destino, datas e preço, mantendo histórico em `seen.json`.

## 4. Custos e limitações
GitHub Pages, Actions e Telegram podem ficar em R$ 0 em uso pessoal e dentro das franquias; fonte de tarifas pode ser paga e exceder R$ 30/mês. Repositório público expõe ofertas e histórico; segredos ficam em Actions Secrets. GitHub cron pode atrasar ou ser suspenso em certas condições. O monitor executa duas vezes por dia, não em tempo real. A integração com Azul Fidelidade não está pronta. Antes de pagar qualquer serviço, confirme acesso à API, cobertura de Recife e termos de uso.
