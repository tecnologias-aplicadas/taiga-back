# Novidades deste fork do Taiga (back-end)

Este repositório é o back-end de um fork do [Taiga 6.8](https://taiga.io), mantido pelo Centro de Tecnologias Aplicadas da Itaipu Parquetec, um centro de tecnologia no Brasil. O código original é da [Kaleidos e do projeto taigaio](https://github.com/taigaio); o fork continua sob a licença AGPL-3, com os créditos preservados.

A descrição completa de cada funcionalidade, com o porquê de cada uma, está no documento de novidades do front: [NEWS-BR.md do taiga-front](https://github.com/ta-iot/taiga-front/blob/main/NEWS-BR.md). Aqui fica só o que o servidor implementa, pois a regra deste fork é que o servidor decide e a interface só reflete.

## O que o back-end implementa

- **Progresso parcial por status de tarefa**, inteiro de 0 a 100 ou vazio; fechado vale 100 e aberto com 100 vira 99.
- **Percentual concluído e em progresso** calculados e recalculados em cascata da tarefa para a história e para a épica; não editáveis pela API.
- **Datas de início, fim previsto e conclusão da épica**, com recusa de fim anterior ao início e conclusão preenchida ao fechar.
- **Cronograma de épicas**: cronogramável e impacto por épica, e um comando de gestão que grava a fotografia mensal sem reescrever meses passados.
- **Relacionamento entre cards** com tipos fixos, uma relação ativa por combinação, histórico nos dois cards, permissão por papel e exclusão lógica.
- **Bloqueio por relação**: card bloqueado não vai para status fechado nem é excluído até a relação ser resolvida.
- **Reações com emoji em comentários**, uma por emoji por membro do projeto, removidas pelo próprio autor.
- **Datas de início, término previsto e término do projeto**, com validação de ordem.
- **Criação de projeto restrita** a administradores e superusuários, projeto privado por padrão.
- **Autenticação em dois caminhos**: conta corporativa pelo diretório institucional (LDAP), conta externa por credencial local, reCAPTCHA nos dois quando ativo; conta corporativa não altera e-mail nem credencial de acesso.
- **Carrossel de novidades da home**: API pública de leitura dos slides ativos e escrita só de superusuário, com validação de imagem, tamanho e limites de texto; nasce vazio em qualquer instalação.
- **Traduções** dos textos do servidor em pt-BR, en e es.

Para o comportamento de cada item e a nota sobre acesso corporativo, veja o NEWS do taiga-front.
